import os

def print_directory_structure(start_path, prefix=''):
    for item in sorted(os.listdir(start_path)):
        path = os.path.join(start_path, item)
        if os.path.isdir(path):
            print(f"{prefix}📁 {item}")
            print_directory_structure(path, prefix + '    ')
        else:
            print(f"{prefix}📄 {item}")

if __name__ == "__main__":
    project_root = r"D:\PhD\dec2025"
    print(f"Project Structure for: {project_root}\n")
    print_directory_structure(project_root)
