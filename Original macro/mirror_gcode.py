# coding: utf-8
import getopt, sys, re

# - Run backend
if __name__ == "__main__":
  try:
    opts, args = getopt.getopt(sys.argv[1:], "s:o:", [])
  except getopt.GetoptError:
    print ('mirror_gcode.py -s <source> -o <destination> ')
    sys.exit(2)

  src_file = ''
  out_file = ''

  # - Parse arguments
  for opt, arg in opts:
    if opt in ("-s", "--source"):
      src_file = arg
    if opt in ("-o", "--output"):
      out_file = arg

  print ("> Reading source file [%s]" % (src_file))

  # - Read source file
  src_data = []
  with open(src_file, 'r') as f:
    src_data = f.read().splitlines()

  out_data = []
  mirror = False
  for line in src_data:
    # - Find task block
    if not mirror:
      # - Direct copy line
      out_data.append(line + "\r\n")

      # - Find task block
      if re.match(r'^;.*(TASK BLOCK)', line):
        mirror = True
        continue
    else:
      # - Replace rotation
      rt = re.search('^(G0[01]) B([\-]{0,1}[0-9]+\.[0-9]+) F([0-9]+\.[0-9]+)', line)
      if rt is not None:
        CM = rt.group(1)
        RT = float(rt.group(2))
        FR = float(rt.group(3))
        out_data.append("%s B%.2f F%.1f\r\n" % (CM, -RT if RT != 0 else 0, FR))
        continue

      mv = re.search(r'^(G0[01]) X([\-]{0,1}[0-9]+\.[0-9]+) Y([\-]{0,1}[0-9]+\.[0-9]+) Z([\-]{0,1}[0-9]+\.[0-9]+) A([\-]{0,1}[0-9]+\.[0-9]+) F([0-9]+\.[0-9]+)', line)
      if mv is not None:
        CM = mv.group(1)
        LX = float(mv.group(2))
        LY = float(mv.group(3))
        RX = float(mv.group(4))
        RY = float(mv.group(5))
        FR = float(mv.group(6))
        out_data.append("%s X%.2f Y%.2f Z%.2f A%.2f F%.1f\r\n" % (CM, RX, RY, LX, LY, FR))
        continue

      # - Direct copy line
      out_data.append(line + "\r\n")


  # - Save file
  with open(out_file, 'w') as f:
    f.writelines(out_data)

  print("> Mirrored GCODE saved to [%s]" % out_file)
