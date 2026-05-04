import os

def list_files(startpath, output_filename="folder_structure.txt"):
    with open(output_filename, "w", encoding="utf-8") as f:
        # Traverse the directory tree recursively
        for root, dirs, files in os.walk(startpath):
            # Calculate depth for indentation
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * level
            
            # Write folder name
            folder_line = f"{indent}{os.path.basename(root)}/\n"
            f.write(folder_line)
            
            # Write file names with additional indentation
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                f.write(f"{subindent}{file}\n")

if __name__ == "__main__":
    # "." represents the current directory
    list_files(".")
    print("Folder tree has been saved to folder_structure.txt")
