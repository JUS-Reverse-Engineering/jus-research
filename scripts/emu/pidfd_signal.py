#!/usr/bin/env python3
"""Send one signal to a pid only if it is still the validated melonDS instance.

Usage: pidfd_signal.py PID START_TOKEN SIGNAME ARGV0_SUFFIX

Linux only. Opens a pidfd first, then checks /proc/PID (argv[0] suffix and
stat field 22), then signals through the pidfd. If the pid was reused before
the pidfd was opened the /proc check fails; if it is reused after, the pidfd
refers to the dead original and the send fails with ESRCH. So a reused PID is
never signalled.

Exit: 0 sent, 3 process gone, 4 identity mismatch, 5 pidfd unavailable or
failed. On 5 nothing was signalled; stop_emu.sh refuses and never falls back.
"""
import os
import signal
import sys


def main():
    pid, start, name, suffix = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    if not (hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')):
        return 5
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return 3
    except OSError:
        return 5
    try:
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as f:
                argv0 = f.read().split(b'\0')[0].decode('utf-8', 'replace')
            with open(f'/proc/{pid}/stat') as f:
                token = f.read().rsplit(')', 1)[1].split()[19]
        except (OSError, IndexError):
            return 3
        if token != start or not (argv0.endswith(suffix) or argv0 == suffix.lstrip('/')):
            return 4
        try:
            signal.pidfd_send_signal(fd, getattr(signal, 'SIG' + name))
        except ProcessLookupError:
            return 3
        except OSError:
            return 5
        return 0
    finally:
        os.close(fd)


if __name__ == '__main__':
    sys.exit(main())
