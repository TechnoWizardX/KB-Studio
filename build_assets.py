import os
import subprocess

def build():

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(base_dir, "src", "resources", "icons")
    qrc_path = os.path.join(base_dir, "src", "resources", "resources.qrc")
    py_path = os.path.join(base_dir, "src", "resources", "resources_rc.py")

    qrc_content = ['<!DOCTYPE RCC><RCC version="1.0">', '  <qresource prefix="icons">']
    
    if os.path.exists(icons_dir):
        for file in os.listdir(icons_dir):
            if file.endswith('.svg') or file.endswith('.png'):
                qrc_content.append(f'    <file>icons/{file}</file>')
                
    qrc_content.extend(['  </qresource>', '</RCC>'])
    
    with open(qrc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(qrc_content))
    print("✓ resources.qrc успешно обновлен.")
    
    try:
        subprocess.run(["pyside6-rcc", qrc_path, "-o", py_path], check=True)
        print("✓ resources_rc.py успешно пересобран!")
    except FileNotFoundError:
        print("Ошибка: Убедитесь, что PySide6 установлен в вашем виртуальном окружении.")

if __name__ == "__main__":
    build()