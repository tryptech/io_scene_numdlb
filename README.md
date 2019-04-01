# Super Smash Bros. Ultimate model and animation importers for Blender (io_scene_numdlb)
Imports data referenced by NUMDLB files and NUANMB files (binary model and animation formats used by some games developed by Bandai-Namco). May work for other games using the same format. Unlike the original MAXScript, this set of scripts is cross-platform, as they will work on any operating system that Blender and Python exist for. The readability in the rewritten model importer script is also improved, with the main function split into several smaller ones.

**The model importer script is now ready for daily use, but the animation importer script is not yet (it can read and import most data, but transformations are not correct). There are a few limitations in the model importer script:**

* Vertex colors are set, but the alpha channel is not used, as there is no way to set it within the Blender UI.

* Animations imported from files may cause meshes to deform incorrectly, most likely because bone roll is not yet properly recalculated.

* The following kinds of textures are read, but currently not imported (the Cycles and EEVEE (2.80 and later) rendering engines may support them however):
    * Normal maps
    * PRM maps
    * Emissive maps

## Where to obtain assets
* Project thread: <https://www.vg-resource.com/thread-34836.html>

* Direct folder (MEGA.nz): <https://mega.nz/#F!AAwWzCjT!Zd5kKpuQcE647DSRtpFShw>

* Direct folder (Google Drive): <https://drive.google.com/open?id=1QucKyF_4IMFvZNZe4mMEiUXiAH5tpTIc>

* PNG textures: <https://gitlab.com/Worldblender/smash-ultimate-textures>

## Installation
This set of two scripts requires Blender 2.70 or later, but only 2.79 has been tested.

1. Clone or download this repository. If downloaded, extract the files after that.

2. Open Blender and select `File -> User Preferences -> Install from File` and select the newly downloaded scripts.

3. In the search bar in the upper left, search for `Super Smash Bros. Ultimate`. If no results are found, try enabling the `Testing` supported level below the search bar.

4. Enable the plugin by clicking the checkbox next to the plugin name.

5. Select `Save User Settings` in the lower left and close the window.

6. Alternate install method: Navigate to the add-ons directory (location depends on OS and setup, see <https://docs.blender.org/manual/en/dev/getting_started/installing/configuration/directories.html> to find out where) at `./scripts/addons/`. If this directory hierarchy does not exist, create it. Copy both of the Python scripts to the add-ons directory. Proceed to step 2 and continue, or press the `F8` key to reload scripts if Blender is already open.

## Removal
1. Open Blender and select `File -> User Preferences -> Add-ons`.

2. In the search bar in the upper left, search for `Super Smash Bros. Ultimate`. If no results are found, try enabling the `Testing` supported level below the search bar.

3. Disable the plugin by clicking the checkbox next to the plugin name - or uninstall the plugin by clicking `Remove`.

4. Select `Save User Settings` in the lower left and close the window.

5. Alternate removal method: Navigate to the add-ons directory (location depends on OS and setup, see <https://docs.blender.org/manual/en/dev/getting_started/installing/configuration/directories.html> to find out where) at `./scripts/addons/`. Delete both scripts beginning with 'SSBUlt'.

## Importing NUMDLB or NUANMB data
1. Navigate to `File -> Import -> NUMDLB` or `File -> Import -> NUANMB` and select the file(s) you wish to import. One at a time for NUMDLB files, and multiple files can be selected for NUANMB animation files.

2. Only if importing NUANMB files, select the armature (skeleton) for the target model before importing them.

3. Select `NUMDLB Import` or `NUANMB Import`, depending on what was selected earlier.

4. If importing data from NUMDLB files, **images are now assigned automatically to UV maps for all meshes if they are located in the same directory as the model files are.** To display these images on meshes, switch the viewport shading option to 'Textured', or open the 3D View properties panel on the right, and select the 'Textured Solid' option in the 'Shading' subpanel.

## Extras
In the *extras* directory are some more scripts. The original MAXScript, a mesh cleanup script, and data read-only scripts can be found here. The data read-only scripts require Blender like the importer scripts do, but they do not require the UI to be open. To run these scripts, type this into a terminal window/command prompt: `blender --background  --python <path-to-script>`, where `blender` may need to be replaced by the full executable path depending on how Blender was installed.
An additional script at <https://github.com/virtualturtle/SSBU_BlenderEaseofImport> can assist in cleaning up meshes by sending expression-specific ones to other layers. I keep an altered copy here so that it can handle more situations than the original author provides.

## Credits
* The NUMDLB importer uses helper functions from the SuperTuxKart SPM importer at <https://sourceforge.net/p/supertuxkart/code/HEAD/tree/media/trunk/blender_26/spm_import.py>.

* Parts of the Python scripts reference snippets of code from <http://steamreview.org/BlenderSourceTools/>.

* The NUANMB importer references code from <https://github.com/SE2Dev/io_anim_seanim>.

* <https://github.com/Ploaj/SSBHLib> - used for checking whether my scripts read the original data correctly or not. The majority of the NUANMB importer references code from here as well.

## License
Everything but the original MAXScript is licensed under the MIT License, found at <./LICENSE>.
