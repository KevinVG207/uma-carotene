# uma-translate-alternative

The main purpose of this repository is to host public translations for the Uma Musume: Pretty Derby game in a way that does not include the original Japanese text, for copyright reasons. As such, in order to create/edit the translations, a working installation of the game is required

The project is a work-in-progress and the focus is currently to convert the mdb translations to the new format.

Translations on this repository are made by KevinVG207, but help is welcome.

The *CODE* of this project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International** license. This means it may be shared and adapted without commercial use. No part of the code of this project may be distributed if a monetary transaction was required before the distribution. (No paywalling.) For more information, see ``LICENSE.md``.

## Requirements
This project assumes the use of Windows 10 (11 not tested.)

The following things need to be installed on your machine:
* Python 3
* Uma Musume: Pretty Derby - DMM version

## Usage

1. Install the required packages using `pip install -r requirements.txt`.
2. Run `src/_update_local.py` to update the local copy of the translations. (Indexing stories may take a few minutes the first time.)
3. Edit the local translations in the `editing` folder.
4. Update the translation files with `src/_prepare_release.py`.

The translations in the `translations` folder will be updated.