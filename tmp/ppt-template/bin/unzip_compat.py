import sys
import zipfile


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "-Z1":
        with zipfile.ZipFile(args[1]) as archive:
            sys.stdout.write("\n".join(archive.namelist()))
            if archive.namelist():
                sys.stdout.write("\n")
        return 0
    if len(args) == 3 and args[0] == "-p":
        with zipfile.ZipFile(args[1]) as archive:
            sys.stdout.buffer.write(archive.read(args[2]))
        return 0
    sys.stderr.write("unsupported unzip arguments: " + repr(args) + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
