import re

# --- 1. PATCH INSTALLER.ISS ---
with open('installer.iss', 'r', encoding='utf-8') as f:
    iss = f.read()

iss = re.sub(r'#define MyAppVersion "7\.0\.0"', 
             r'#ifndef MyAppVersion\n#define MyAppVersion "7.0.0"\n#endif', iss)

iss = re.sub(r'OutputBaseFilename=DariusAI-Setup-v7\.0\.0', 
             r'#ifndef MyOutputBaseFilename\n#define MyOutputBaseFilename "DariusAI-Setup-v7.0.0"\n#endif\nOutputBaseFilename={#MyOutputBaseFilename}', iss)

with open('installer.iss', 'w', encoding='utf-8') as f:
    f.write(iss)


# --- 2. PATCH RELEASE.YML ---
with open('.github/workflows/release.yml', 'r', encoding='utf-8') as f:
    yml = f.read()

inno_old = r'''      - name: Compilar Instalador de Windows con Inno Setup
        run: |
          mkdir dist-installer -Force
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss'''

inno_new = r'''      - name: Compilar Instalador de Windows con Inno Setup
        run: |
          mkdir dist-installer -Force
          $TAG = "${{ github.ref_name }}"
          if (!$TAG -or $TAG -eq "") { $TAG = "${{ inputs.tag_name }}" }
          $RAW_VERSION = $TAG.TrimStart('v')
          & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DMyAppVersion=$RAW_VERSION" "/DMyOutputBaseFilename=DariusAI-Setup-$TAG" installer.iss'''

yml = yml.replace(inno_old, inno_new)

zip_old = r'''      - name: Generar paquete portable .ZIP
        run: |
          Compress-Archive -Path dist\main.dist\* -DestinationPath dist-installer\DariusAI-v7.0.0-windows-x64-portable.zip -Force'''

zip_new = r'''      - name: Generar paquete portable .ZIP
        run: |
          $TAG = "${{ github.ref_name }}"
          if (!$TAG -or $TAG -eq "") { $TAG = "${{ inputs.tag_name }}" }
          Compress-Archive -Path dist\main.dist\* -DestinationPath "dist-installer\DariusAI-$TAG-windows-x64-portable.zip" -Force'''

yml = yml.replace(zip_old, zip_new)

yml = yml.replace('name: Darius AI v7.0.0', 'name: Darius AI ${{ github.ref_name || inputs.tag_name }}')

files_old = r'''          files: |
            dist-installer/DariusAI-Setup-v7.0.0.exe
            dist-installer/DariusAI-v7.0.0-windows-x64-portable.zip'''

files_new = r'''          files: |
            dist-installer/DariusAI-Setup-*.exe
            dist-installer/DariusAI-*-windows-x64-portable.zip'''

yml = yml.replace(files_old, files_new)

with open('.github/workflows/release.yml', 'w', encoding='utf-8') as f:
    f.write(yml)

print("CI/CD pipeline refactored successfully.")
