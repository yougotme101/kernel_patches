import sys
import os

def patch_file(filepath, replacements):
    print(f"Patching {filepath}...")
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found!")
        sys.exit(1)
        
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    for target, replacement in replacements:
        if target not in content:
            print(f"Error: Target text not found in {filepath}!")
            print("--- TARGET ---")
            print(target)
            print("--------------")
            sys.exit(1)
        content = content.replace(target, replacement, 1)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Successfully patched {filepath}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 patch_gki.py <kernel_source_dir>")
        sys.exit(1)
        
    kernel_dir = sys.argv[1]
    
    # ----------------------------------------------------
    # Patches for fs/namespace.c
    # ----------------------------------------------------
    namespace_path = os.path.join(kernel_dir, "fs/namespace.c")
    namespace_replacements = [
        # Replacement 1: Include block
        (
            '#include <linux/mnt_idmapping.h>',
            '#include <linux/mnt_idmapping.h>\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '#include <linux/susfs_def.h>\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT'
        ),
        # Replacement 2: Declaration block
        (
            '#include "internal.h"',
            '#include "internal.h"\n\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            'extern bool susfs_is_current_ksu_domain(void);\n'
            'extern struct static_key_true susfs_is_sdcard_android_data_not_decrypted;\n\n'
            '#define CL_COPY_MNT_NS BIT(25) /* used by copy_mnt_ns() */\n\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT'
        ),
        # Replacement 3: mnt_free_id
        (
            'static void mnt_free_id(struct mount *mnt)\n'
            '{\n'
            '\treturn;\n'
            '}',
            'static void mnt_free_id(struct mount *mnt)\n'
            '{\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\tif (mnt->mnt.mnt_flags & VFSMOUNT_MNT_FLAGS_KSU_UNSHARED_MNT)\n'
            '\t\treturn;\n\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\treturn;\n'
            '}'
        ),
        # Replacement 4: mnt_alloc_group_id
        (
            'static int mnt_alloc_group_id(struct mount *mnt)\n'
            '{\n'
            '\treturn 0;\n'
            '}',
            'static int mnt_alloc_group_id(struct mount *mnt)\n'
            '{\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\tint res;\n\n'
            '\t/* - mnt_alloc_group_id will unlikely get called after screen is unlocked on reboot,\n'
            '\t *   so here we can persistently check if current is ksu domain, and assign a sus\n'
            '\t *   mnt_group_id if so.\n'
            '\t * - Also we can re-use the original mnt_group_ida so there is no need to use\n'
            '\t *   another ida nor hook the mnt_release_group_id() function.\n'
            '\t */\n'
            '\tif (susfs_is_current_ksu_domain()) {\n'
            '\t\tres = ida_alloc_min(&mnt_group_ida, DEFAULT_KSU_MNT_GROUP_ID, GFP_KERNEL);\n'
            '\t\tgoto bypass_orig_flow;\n'
            '\t}\n\n'
            '\tres = 0;\n'
            'bypass_orig_flow:\n'
            '#else\n'
            '\tint res = 0;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\n'
            '\tif (res < 0)\n'
            '\t\treturn res;\n'
            '\tmnt->mnt_group_id = res;\n'
            '\treturn 0;\n'
            '}'
        ),
        # Replacement 5: alloc_vfsmnt helpers
        (
            'static struct mount *alloc_vfsmnt(const char *name)',
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '/* A copy of alloc_vfsmnt() but allocates the fake mnt_id for mounts\n'
            ' * that are unshared by ksu process\n'
            ' */\n'
            'static struct mount *susfs_alloc_unshare_ksu_vfsmnt(const char *name, int old_mnt_id)\n'
            '{\n'
            '\tstruct mount *mnt = kmem_cache_zalloc(mnt_cache, GFP_KERNEL);\n\n'
            '\tif (mnt) {\n'
            '\t\tmnt->mnt_id = old_mnt_id;\n\n'
            '\t\tif (name) {\n'
            '\t\t\tmnt->mnt_devname = kstrdup_const(name,\n'
            '\t\t\t\t\t\t\t GFP_KERNEL_ACCOUNT);\n'
            '\t\t\tif (!mnt->mnt_devname)\n'
            '\t\t\t\tgoto out_free_cache;\n'
            '\t\t}\n\n'
            '#ifdef CONFIG_SMP\n'
            '\t\tmnt->mnt_pcp = alloc_percpu(struct mnt_pcp);\n'
            '\t\tif (!mnt->mnt_pcp)\n'
            '\t\t\tgoto out_free_devname;\n\n'
            '\t\tthis_cpu_add(mnt->mnt_pcp->mnt_count, 1);\n'
            '#else\n'
            '\t\tmnt->mnt_count = 1;\n'
            '\t\tmnt->mnt_writers = 0;\n'
            '#endif\n\n'
            '\t\tINIT_HLIST_NODE(&mnt->mnt_hash);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_child);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_mounts);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_list);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_expire);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_share);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_slave_list);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_slave);\n'
            '\t\tINIT_HLIST_NODE(&mnt->mnt_mp_list);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_umounting);\n'
            '\t\tINIT_HLIST_HEAD(&mnt->mnt_stuck_children);\n'
            '\t\tmnt->mnt.mnt_userns = &init_user_ns;\n'
            '\t}\n'
            '\treturn mnt;\n\n'
            '#ifdef CONFIG_SMP\n'
            'out_free_devname:\n'
            '\tkfree_const(mnt->mnt_devname);\n'
            '#endif\n'
            'out_free_cache:\n'
            '\tkmem_cache_free(mnt_cache, mnt);\n'
            '\treturn NULL;\n'
            '}\n\n'
            '/* A copy of alloc_vfsmnt() but allocates the fake mnt_id for mount\n'
            ' * that is mounted or single cloned by ksu process\n'
            ' */\n'
            'static struct mount *susfs_alloc_non_unshare_ksu_vfsmnt(const char *name)\n'
            '{\n'
            '\tstruct mount *mnt = kmem_cache_zalloc(mnt_cache, GFP_KERNEL);\n'
            '\tint res;\n\n'
            '\tif (mnt) {\n'
            '\t\tres = ida_alloc_min(&mnt_id_ida, DEFAULT_KSU_MNT_ID, GFP_KERNEL);\n'
            '\t\tif (res < 0)\n'
            '\t\t\tgoto out_free_cache;\n\n'
            '\t\tmnt->mnt_id = res;\n\n'
            '\t\tif (name) {\n'
            '\t\t\tmnt->mnt_devname = kstrdup_const(name,\n'
            '\t\t\t\t\t\t\t GFP_KERNEL_ACCOUNT);\n'
            '\t\t\tif (!mnt->mnt_devname)\n'
            '\t\t\t\tgoto out_free_id;\n'
            '\t\t}\n\n'
            '#ifdef CONFIG_SMP\n'
            '\t\tmnt->mnt_pcp = alloc_percpu(struct mnt_pcp);\n'
            '\t\tif (!mnt->mnt_pcp)\n'
            '\t\t\tgoto out_free_devname;\n\n'
            '\t\tthis_cpu_add(mnt->mnt_pcp->mnt_count, 1);\n'
            '#else\n'
            '\t\tmnt->mnt_count = 1;\n'
            '\t\tmnt->mnt_writers = 0;\n'
            '#endif\n\n'
            '\t\tINIT_HLIST_NODE(&mnt->mnt_hash);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_child);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_mounts);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_list);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_expire);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_share);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_slave_list);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_slave);\n'
            '\t\tINIT_HLIST_NODE(&mnt->mnt_mp_list);\n'
            '\t\tINIT_LIST_HEAD(&mnt->mnt_umounting);\n'
            '\t\tINIT_HLIST_HEAD(&mnt->mnt_stuck_children);\n'
            '\t\tmnt->mnt.mnt_userns = &init_user_ns;\n'
            '\t}\n'
            '\treturn mnt;\n\n'
            '#ifdef CONFIG_SMP\n'
            'out_free_devname:\n'
            '\tkfree_const(mnt->mnt_devname);\n'
            '#endif\n'
            'out_free_id:\n'
            '\tmnt_free_id(mnt);\n'
            'out_free_cache:\n'
            '\tkmem_cache_free(mnt_cache, mnt);\n'
            '\treturn NULL;\n'
            '}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\n'
            'static struct mount *alloc_vfsmnt(const char *name)'
        ),
        # Replacement 6: vfs_create_mount
        (
            '\tmnt = alloc_vfsmnt(fc->source ?: "none");',
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\t// - We will just stop checking for ksu process if /sdcard/Android is accessible,\n'
            '\t//   for the sake of performance\n'
            '\tif (static_branch_unlikely(&susfs_is_sdcard_android_data_not_decrypted)) {\n'
            '\t\tif (susfs_is_current_ksu_domain()) {\n'
            '\t\t\tmnt = susfs_alloc_non_unshare_ksu_vfsmnt(fc->source ?: "none");\n'
            '\t\t\tgoto bypass_orig_flow;\n'
            '\t\t}\n'
            '\t}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\n'
            '\tmnt = alloc_vfsmnt(fc->source ?: "none");\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            'bypass_orig_flow:\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT'
        ),
        # Replacement 7: clone_mnt start
        (
            'static struct mount *clone_mnt(struct mount *old, struct dentry *root,\n'
            '\t\t\t\t\tint flag)\n'
            '{\n'
            '\tstruct super_block *sb = old->mnt.mnt_sb;\n'
            '\tstruct mount *mnt;\n'
            '\tint err;\n\n'
            '\tmnt = alloc_vfsmnt(old->mnt_devname);',
            'static struct mount *clone_mnt(struct mount *old, struct dentry *root,\n'
            '\t\t\t\t\tint flag)\n'
            '{\n'
            '\tstruct super_block *sb = old->mnt.mnt_sb;\n'
            '\tstruct mount *mnt;\n'
            '\tint err;\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\tbool is_mnt_ksu_unshared = false;\n\n'
            '\t// - We will just stop checking for ksu process if /sdcard/Android is accessible,\n'
            '\t//   for the sake of performance\n'
            '\tif (static_branch_unlikely(&susfs_is_sdcard_android_data_not_decrypted)) {\n'
            '\t\t// - If /sdcard/Android is still not accessible, we keep checking for mounts\n'
            '\t\t//   mounted by ksu process\n'
            '\t\tif (susfs_is_current_ksu_domain()) {\n'
            '\t\t\t// - If it is unsharing, we re-use the old->mnt_id assign it for mnt->mnt_id directly\n'
            '\t\t\t//   without going thru ida, but we need to set a bit VFSMOUNT_MNT_FLAGS_KSU_UNSHARED_MNT\n'
            '\t\t\t//   on mnt->mnt.mnt_flags below, otherwise we find no other ways to identify if this\n'
            '\t\t\t//   mnt->mnt_id is assigned without ida when it is being freed in mnt_free_id().\n'
            '\t\t\tif (flag & CL_COPY_MNT_NS) {\n'
            '\t\t\t\tmnt = susfs_alloc_unshare_ksu_vfsmnt(old->mnt_devname, old->mnt_id);\n'
            '\t\t\t\tis_mnt_ksu_unshared = true;\n'
            '\t\t\t\tgoto bypass_orig_flow;\n'
            '\t\t\t}\n'
            '\t\t\t// else we just go assign fake mnt_id starting with DEFAULT_KSU_MNT_ID\n'
            '\t\t\tmnt = susfs_alloc_non_unshare_ksu_vfsmnt(old->mnt_devname);\n'
            '\t\t\t\tgoto bypass_orig_flow;\n'
            '\t\t}\n'
            '\t}\n\n'
            '\t// - We keep checking all processes and if old->mnt_id >= DEFAULT_KSU_MNT_ID,\n'
            '\t//   go assign fake mnt_id starting with DEFAULT_KSU_MNT_ID\n'
            '\tif (old->mnt_id >= DEFAULT_KSU_MNT_ID) {\n'
            '\t\tmnt = susfs_alloc_non_unshare_ksu_vfsmnt(old->mnt_devname);\n'
            '\t\t\tgoto bypass_orig_flow;\n'
            '\t}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\n'
            '\tmnt = alloc_vfsmnt(old->mnt_devname);\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            'bypass_orig_flow:\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT'
        ),
        # Replacement 8: clone_mnt flags setting
        (
            '\tmnt->mnt.mnt_flags = old->mnt.mnt_flags;\n'
            '\tmnt->mnt.mnt_flags &= ~(MNT_WRITE_HOLD|MNT_MARKED|MNT_INTERNAL);\n\n'
            '\tatomic_inc(&sb->s_active);',
            '\tmnt->mnt.mnt_flags = old->mnt.mnt_flags;\n'
            '\tmnt->mnt.mnt_flags &= ~(MNT_WRITE_HOLD|MNT_MARKED|MNT_INTERNAL);\n\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\tif (unlikely(is_mnt_ksu_unshared))\n'
            '\t\tmnt->mnt.mnt_flags |= VFSMOUNT_MNT_FLAGS_KSU_UNSHARED_MNT;\n\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n\n'
            '\tatomic_inc(&sb->s_active);'
        ),
        # Replacement 9: copy_mnt_ns flags
        (
            '\tcopy_flags = CL_COPY_UNBINDABLE | CL_EXPIRE;\n'
            '\tif (user_ns != ns->user_ns)\n'
            '\t\tcopy_flags |= CL_SHARED_TO_SLAVE;\n'
            '\tnew = copy_tree(old, old->mnt.mnt_root, copy_flags);',
            '\tcopy_flags = CL_COPY_UNBINDABLE | CL_EXPIRE;\n'
            '\tif (user_ns != ns->user_ns)\n'
            '\t\tcopy_flags |= CL_SHARED_TO_SLAVE;\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\tcopy_flags |= CL_COPY_MNT_NS;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '\tnew = copy_tree(old, old->mnt.mnt_root, copy_flags);'
        ),
        # Replacement 10: Appended helpers at the end of the file
        (
            'const struct proc_ns_operations mntns_operations = {\n'
            '\t.name\t\t= "mnt",\n'
            '\t.type\t\t= CLONE_NEWNS,\n'
            '\t.get\t\t= mntns_get,\n'
            '\t.put\t\t= mntns_put,\n'
            '\t.install\t= mntns_install,\n'
            '\t.owner\t\t= mntns_owner,\n'
            '};',
            'const struct proc_ns_operations mntns_operations = {\n'
            '\t.name\t\t= "mnt",\n'
            '\t.type\t\t= CLONE_NEWNS,\n'
            '\t.get\t\t= mntns_get,\n'
            '\t.put\t\t= mntns_put,\n'
            '\t.install\t= mntns_install,\n'
            '\t.owner\t\t= mntns_owner,\n'
            '};\n\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
            '/* - To retrieve the non sus mnt_id from mount */\n'
            'int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt) {\n'
            '\tstruct mount *mnt = orig_mnt;\n'
            '\tint mnt_id;\n\n'
            '\tlock_mount_hash();\n'
            '\tfor (; mnt && mnt->mnt_parent && mnt != mnt->mnt_parent && mnt->mnt_id >= DEFAULT_KSU_MNT_ID; mnt = mnt->mnt_parent) { }\n'
            '\tmnt_id = mnt->mnt_id;\n'
            '\tunlock_mount_hash();\n'
            '\treturn mnt_id;\n'
            '}\n\n'
            '/* - To retrieve the non sus vfsmount from vfsmount, takes a reference on &mnt->mnt and mnt->mnt.mnt_root */\n'
            'struct vfsmount *susfs_get_non_sus_vfsmnt_from_vfsmnt(struct vfsmount *vfsmnt) {\n'
            '\tstruct mount *mnt = real_mount(vfsmnt);\n\n'
            '\tlock_mount_hash();\n'
            '\tfor (; mnt && mnt->mnt_parent && mnt != mnt->mnt_parent && mnt->mnt_id >= DEFAULT_KSU_MNT_ID; mnt = mnt->mnt_parent) { }\n'
            '\tmntget(&mnt->mnt);\n'
            '\tif (!mnt->mnt.mnt_root || IS_ERR(mnt->mnt.mnt_root)) {\n'
            '\t\tmntput(&mnt->mnt);\n'
            '\t\tunlock_mount_hash();\n'
            '\t\treturn vfsmnt;\n'
            '\t}\n'
            '\tdget(mnt->mnt.mnt_root);\n'
            '\tunlock_mount_hash();\n'
            '\treturn &mnt->mnt;\n'
            '}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT'
        )
    ]
    patch_file(namespace_path, namespace_replacements)

    # ----------------------------------------------------
    # Patches for fs/proc/task_mmu.c
    # ----------------------------------------------------
    task_mmu_path = os.path.join(kernel_dir, "fs/proc/task_mmu.c")
    task_mmu_replacements = [
        # Replacement 1: Include block
        (
            '#include <linux/pkeys.h>',
            '#include <linux/pkeys.h>\n'
            '#if defined(CONFIG_KSU_SUSFS_SUS_KSTAT) || defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)\n'
            '#include <linux/susfs_def.h>\n'
            '#endif // #if defined(CONFIG_KSU_SUSFS_SUS_KSTAT) || defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)'
        ),
        # Replacement 2: externs declaration before show_map_vma
        (
            'static void\n'
            'show_map_vma(struct seq_file *m, struct vm_area_struct *vma)\n'
            '{',
            '#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n'
            'extern void susfs_sus_kstat_spoof_show_map_vma(struct inode *inode, dev_t *out_dev, unsigned long *out_ino);\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n'
            '#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
            'extern int susfs_open_redirect_spoof_show_map_vma(struct inode *inode, unsigned long *out_ino, dev_t *out_dev, char *spoofed_name);\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\n'
            'static void\n'
            'show_map_vma(struct seq_file *m, struct vm_area_struct *vma)\n'
            '{'
        ),
        # Replacement 3: spoofed name declaration in show_map_vma
        (
            '\tunsigned long start, end;\n'
            '\tdev_t dev = 0;\n'
            '\tconst char *name = NULL;\n\n'
            '\tif (file) {',
            '\tunsigned long start, end;\n'
            '\tdev_t dev = 0;\n'
            '\tconst char *name = NULL;\n'
            '#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
            '\tchar *spoofed_redirected_name = NULL;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\n'
            '\tif (file) {'
        ),
        # Replacement 4: body changes inside show_map_vma (file handling)
        (
            '\tif (file) {\n'
            '\t\tstruct inode *inode = file_inode(vma->vm_file);\n'
            '\t\tdev = inode->i_sb->s_dev;\n'
            '\t\tino = inode->i_ino;\n'
            '\t\tpgoff = ((loff_t)vma->vm_pgoff) << PAGE_SHIFT;\n'
            '\t}\n\n'
            '\tstart = vma->vm_start;',
            '\tif (file) {\n'
            '\t\tstruct inode *inode = file_inode(vma->vm_file);\n'
            '#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
            '\t\tif (SUSFS_IS_INODE_OPEN_REDIRECT(inode)) {\n'
            '\t\t\tif (!susfs_open_redirect_spoof_show_map_vma(inode, &ino, &dev, spoofed_redirected_name)) {\n'
            '\t\t\t\tpgoff = ((loff_t)vma->vm_pgoff) << PAGE_SHIFT;\n'
            '\t\t\t\tgoto orig_flow;\n'
            '\t\t\t}\n'
            '\t\t}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tif (SUSFS_IS_INODE_SUS_MAP(inode))\n'
            '\t\t\treturn;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tdev = inode->i_sb->s_dev;\n'
            '\t\tino = inode->i_ino;\n'
            '\t\tpgoff = ((loff_t)vma->vm_pgoff) << PAGE_SHIFT;\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n'
            '\t\tsusfs_sus_kstat_spoof_show_map_vma(inode, &dev, &ino);\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n'
            '\t}\n\n'
            '#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
            'orig_flow:\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\n'
            '\tstart = vma->vm_start;'
        ),
        # Replacement 5: spoofed name printing inside show_map_vma
        (
            '\tif (file) {\n'
            '\t\tseq_pad(m, \' \');\n'
            '\t\tseq_file_path(m, file, "\\n");\n'
            '\t} else if (vma->vm_start <= VMA_PAD_START(vma)) {',
            '#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n'
            '\tif (spoofed_redirected_name) {\n'
            '\t\tseq_pad(m, \' \');\n'
            '\t\tseq_puts(m, spoofed_redirected_name);\n'
            '\t\tseq_putc(m, \'\\n\');\n'
            '\t\tkfree(spoofed_redirected_name);\n'
            '\t\treturn;\n'
            '\t}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT\n\n'
            '\tif (file) {\n'
            '\t\tseq_pad(m, \' \');\n'
            '\t\tseq_file_path(m, file, "\\n");\n'
            '\t} else if (vma->vm_start <= VMA_PAD_START(vma)) {'
        ),
        # Replacement 6: show_smap skip sus_map
        (
            'static int show_smap(struct seq_file *m, void *v)\n'
            '{\n'
            '\tstruct vm_area_struct *vma = v;\n'
            '\tstruct mem_size_stats mss;\n\n'
            '\tmemset(&mss, 0, sizeof(mss));',
            'static int show_smap(struct seq_file *m, void *v)\n'
            '{\n'
            '\tstruct vm_area_struct *vma = v;\n'
            '\tstruct mem_size_stats mss;\n\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\tif (vma->vm_file) {\n'
            '\t\tif (SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n'
            '\t\t\treturn 0;\n'
            '\t}\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n\n'
            '\tmemset(&mss, 0, sizeof(mss));'
        ),
        # Replacement 7: show_smaps_rollup loop bypass
        (
            '\tfor (vma = priv->mm->mmap; vma;) {\n'
            '\t\tsmap_gather_stats(vma, &mss, 0);\n'
            '\t\tlast_vma_end = vma->vm_end;',
            '\tfor (vma = priv->mm->mmap; vma;) {\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tif (vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n'
            '\t\t\tgoto bypass_orig_flow;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tsmap_gather_stats(vma, &mss, 0);\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            'bypass_orig_flow:\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tlast_vma_end = vma->vm_end;'
        ),
        # Replacement 8: show_smaps_rollup case 4
        (
            '\t\t\t/* Case 4 above */\n'
            '\t\t\tif (vma->vm_end > last_vma_end)\n'
            '\t\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);\n'
            '\t\t}',
            '\t\t\t/* Case 4 above */\n'
            '\t\t\tif (vma->vm_end > last_vma_end)\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\t\t{\n'
            '\t\t\t\tif (!vma->vm_file || !(SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file))))\n'
            '\t\t\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);\n'
            '\t\t\t}\n'
            '#else\n'
            '\t\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\t}'
        ),
        # Replacement 9: pagemap_read struct vm_area_struct vma
        (
            '\twhile (count && (start_vaddr < end_vaddr)) {\n'
            '\t\tint len;\n'
            '\t\tunsigned long end;\n\n'
            '\t\tpm.pos = 0;',
            '\twhile (count && (start_vaddr < end_vaddr)) {\n'
            '\t\tint len;\n'
            '\t\tunsigned long end;\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tstruct vm_area_struct *vma;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n\n'
            '\t\tpm.pos = 0;'
        ),
        # Replacement 10: pagemap_read walk_page_range bypass
        (
            '\t\tret = mmap_read_lock_killable(mm);\n'
            '\t\tif (ret)\n'
            '\t\t\tgoto out_free;\n'
            '\t\tret = walk_page_range(mm, start_vaddr, end, &pagemap_ops, &pm);\n'
            '\t\tmmap_read_unlock(mm);',
            '\t\tret = mmap_read_lock_killable(mm);\n'
            '\t\tif (ret)\n'
            '\t\t\tgoto out_free;\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tvma = vma_lookup(mm, start_vaddr);\n'
            '\t\tif (vma && vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))\n'
            '\t\t\tgoto bypass_orig_flow;\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tret = walk_page_range(mm, start_vaddr, end, &pagemap_ops, &pm);\n'
            '#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            'bypass_orig_flow:\n'
            '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP\n'
            '\t\tmmap_read_unlock(mm);'
        )
    ]
    patch_file(task_mmu_path, task_mmu_replacements)

if __name__ == "__main__":
    main()
