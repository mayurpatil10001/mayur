import os

path = r"C:\SierraChart\SC results WF"
with open("file_list.txt", "w") as f:
    for root, dirs, files in os.walk(path):
        for name in files:
            f.write(os.path.join(root, name) + "\n")
