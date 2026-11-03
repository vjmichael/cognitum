#define _GNU_SOURCE
/* CH36 test-only glibc interception. No filesystem is mounted or modified.
 * Inject a kernel-facing fsync failure on the selected target pathname,
 * after real write/rename operations and before the requested durability fence.
 * This does NOT prove a physical disk-full or hardware power cut.
 */
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static int (*real_fsync)(int) = NULL;
int fsync(int fd) {
    if (!real_fsync) real_fsync = (int (*)(int))dlsym(RTLD_NEXT, "fsync");
    if (!real_fsync) { errno = EIO; return -1; }
    const char *match = getenv("CH36_FSYNC_TARGET");
    const char *code = getenv("CH36_FSYNC_ERRNO");
    if (match && code) {
        char link[64],path[PATH_MAX];
        snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
        ssize_t n = readlink(link, path, sizeof(path)-1);
        if (n > 0) {
            path[n] = '\0';
            const char *base = strrchr(path, '/'); base = base ? base + 1 : path;
            int select = 0;
            if (!strncmp(match,"prefix:",7)) select = !strncmp(base, match+7, strlen(match+7));
            else if (!strncmp(match,"exact:",6)) select = !strcmp(path, match+6);
            if (select) {
                int e=atoi(code);
                if (e==ENOSPC || e==EIO || e==EDQUOT) { errno=e; return -1; }
            }
        }
    }
    return real_fsync(fd);
}
