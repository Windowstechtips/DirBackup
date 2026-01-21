# DirBackup

A Python-based directory backup utility with a smart Restore Preview and Profile management system.

## Features

- **Profile Management**: Create and switch between different backup sets (e.g., "Work", "Personal").
- **Smart Restore**: View exactly what files will be restored and if they will overwrite existing files before confirming.
- **Admin Privilege Handling**: Automatically requests elevation if restoring to protected directories.
- **Portable**: Built as a single-file executable.

## Installation

1.  Download the latest release from the [Releases](../../releases) page.
2.  Run `DirBackup.exe`.

## Development

1.  Install Python 3.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the app:
    ```bash
    python backup_app.py
    ```

## Building

To build the executable:

```bash
pyinstaller DirBackup.spec
```

The output will be in the `dist` folder.
