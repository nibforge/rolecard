# Install rolecard without the terminal

[Español](install.es.md) · [Home](index.md) · [Guide](guide.en.md)

This guide is for you if you have never used a terminal or a programming tool. You will
not type any commands: you download a file, double-click it and use rolecard in your
browser.

rolecard needs one thing installed on your computer: **Python**, the free program
rolecard runs on. You install it once, following the steps below. The first time takes
about 10 minutes; after that, rolecard opens in a few seconds.

## What you need

- A computer with Windows or macOS (Linux works too).
- An internet connection the first time.
- Python 3.12 or newer. If you are not sure whether you have it, follow the next
  section anyway: installing it again does no harm.

## 1. Install Python on Windows

1. Open [python.org/downloads](https://www.python.org/downloads/).
2. Click **Download Python install manager**. If the page shows a button
   **Download Python 3.x.y** for Windows instead, click that one.
3. Open the file you downloaded and click **Install**.
4. If a screen shows the box **Add python.exe to PATH**, tick it. (PATH is the list of
   places where Windows looks for programs; ticking it lets rolecard find Python.)
5. If it asks whether to add a folder to your PATH, answer yes.
6. When it says it has finished, close it.

Official source: [Using Python on Windows](https://docs.python.org/3/using/windows.html#python-install-manager).
With the install manager, Python may finish installing itself the first time you open
rolecard and ask you a question in the black window: answer yes.

## 2. Install Python on macOS

1. Open [python.org/downloads](https://www.python.org/downloads/).
2. Click the yellow button **Download Python 3.x.y**.
3. Open the downloaded `.pkg` file and follow the steps (**Continue**, **Agree**,
   **Install**).
4. When it says it has finished, close it.

Official source: [Using Python on macOS](https://docs.python.org/3/using/mac.html#installation-steps).

## 3. Download rolecard

1. Download [rolecard.zip](https://github.com/nibforge/rolecard/releases/latest/download/rolecard.zip).
2. On Windows, open your **Downloads** folder, right-click `rolecard.zip` and choose
   **Extract All…**, then **Extract**. Do not open anything from inside the zip: it
   will not work.
3. On macOS, double-click `rolecard.zip` in **Downloads**: a `rolecard` folder appears
   next to it.
4. If you like, move the `rolecard` folder somewhere handy, such as **Documents**.

How to unzip on Windows, from Microsoft: [Zip and unzip files](https://support.microsoft.com/windows/zip-and-unzip-files-8d28fa72-f2f9-712f-67df-f80cf89fd4e5).

## 4. Open rolecard

1. Open the `rolecard` folder.
2. Double-click **Iniciar rolecard** ("Iniciar" means "Start"): `Iniciar rolecard.bat`
   on Windows, `Iniciar rolecard.command` on macOS. On Linux, run `start.sh`.
3. The first time, a black window says "Preparing rolecard (first time only)…" while it
   downloads what rolecard needs. Wait a few minutes.
4. On Windows, it then asks whether to create a "rolecard" shortcut on your desktop:
   type Y and press Enter (or N if you do not want it).
5. rolecard opens in your browser. That's it.

If Windows or macOS shows a security warning instead, see the next section.

## 5. Security warnings you may see

rolecard is new and free, so it is not signed by a company that Microsoft or Apple
knows. The first time, your computer may warn you. This is expected.

### Windows: "Windows protected your PC"

1. Click **More info**.
2. Click **Run anyway**.

It only appears the first time. What this warning is, from Microsoft:
[Microsoft Defender SmartScreen](https://learn.microsoft.com/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/).

### macOS: "Iniciar rolecard.command" cannot be opened

1. Click **Done** (or **OK**) to close the warning.
2. Open the Apple menu, then **System Settings**, then **Privacy & Security**.
3. Under **Security**, click **Open Anyway** (it is there for about an hour after the
   warning).
4. Type your Mac password and click **OK**.

From then on it opens with a double-click. On older versions of macOS, Control-click the
file and choose **Open** instead. Apple explains both:
[Open a Mac app from an unknown developer](https://support.apple.com/guide/mac-help/mh40616/mac).

## 6. The black window

The black window (a terminal: a window where programs show text) is rolecard itself
running. Your browser talks to it at `http://127.0.0.1:8765`, an address that only your
computer can open. It says "rolecard is open in your browser". Keep it open while you
use rolecard; you can minimise it.

If you close only the browser tab, rolecard keeps running in the black window. To get
back, double-click **Iniciar rolecard** again: it notices rolecard is already open and
just opens your browser.

## 7. Close rolecard

- Click **Quit** at the bottom of the left menu. The page says "rolecard has closed";
  now close the tab.
- Or close the black window.

Your work is saved as you go, so you lose nothing either way.

## 8. Open it another day

- Double-click the **rolecard** shortcut on your desktop (Windows, if you created it),
  or **Iniciar rolecard** in the `rolecard` folder.
- It opens in a few seconds: the preparation only happens the first time.

## 9. Update to a new version

Your data is not in the `rolecard` folder: it is in a folder called `.rolecard` inside
your user folder. Updating does not touch it.

1. Close rolecard (**Quit**).
2. Download the new [rolecard.zip](https://github.com/nibforge/rolecard/releases/latest/download/rolecard.zip)
   and extract it, as in step 3.
3. Delete the old `rolecard` folder and put the new one in the same place (so the
   desktop shortcut keeps working).
4. Double-click **Iniciar rolecard**. It prepares itself again, once.

To keep a copy of your data first: on Windows, open File Explorer, type
`%USERPROFILE%\.rolecard` in the address bar and copy that folder; on macOS, in Finder
press Cmd+Shift+G, type `~/.rolecard` and copy it.

## If something goes wrong

- **"rolecard needs Python 3.12 or newer"**: install Python (step 1 or 2), close the
  black window and double-click **Iniciar rolecard** again.
- **"Something went wrong" while preparing**: check your internet connection and
  double-click **Iniciar rolecard** again.
- **Nothing happens on macOS**: see the macOS warning in step 5.
- Anything else: the black window stays open with the message. Write it down or take a
  screenshot, and [open an issue](https://github.com/nibforge/rolecard/issues).
