# -*- coding: utf-8 -*-
# Manage Kodi Favourites program add-on for Kodi 17.6+.
# Lets you see and manage your Kodi favourites, to organize them.
# In other words, this is an add-on to edit your
# favourites.xml file.
#
# --------------------------------------------------------------------
# M-Borsch 2026-02-14: Version 2.0.0
# - Initial Release based on 1.4.3 of Insert/Swap Kodi Favourites.
# - Complete re-write of the Addon to allow for the ability to add
# prefixes and suffixes and color items in your Kodi Favoutites list
# --------------------------------------------------------------------
# M-Borsch 2023-12-24: Version 1.4.3
# - Updated to include Thumb size settings.
# - Must have 2 versions of the skin - ! for large and 1 for small thumbs
# --------------------------------------------------------------------
# M-Borsch 2023-12-24: Version 1.4.2
# - Updated to include Font size settings.
# --------------------------------------------------------------------
# M-Borsch 2023-12-23: Version 1.4.1
# - Updated to optimize reading of renderMethod
# - define renderMethod as Window property to allow modal dialog to
#   use to be contextual.
# --------------------------------------------------------------------
#
# ====================================================================
import re
import sys
import json
import traceback
import xbmc
import xbmcgui
import os
import shutil
import xbmcvfs

try:
    # Python 2.x
    from HTMLParser import HTMLParser
    PARSER = HTMLParser()
    DECODE_STRING = lambda val: val.decode('utf-8')
except ImportError as e:
    # Python 3.4+ (see https://stackoverflow.com/a/2360639)
    import html
    PARSER = html
    DECODE_STRING = lambda val: val # Pass-through.

import xbmc, xbmcgui, xbmcplugin, xbmcvfs
from xbmcaddon import Addon

DEBUG = '0'
DEBUG2 = '1'
# Flag to put up the Under Construction Popup
DEBUG3 = '0'
FAVOURITES_PATH = 'special://userdata/favourites.xml'
NEW_FAVOURITES_PATH = 'special://userdata/favourites-new.xml'
THUMBNAILS_PATH_FORMAT = 'special://thumbnails/{folder}/{file}'

PROPERTY_FAVOURITES_RESULT = 'managefav.result'
REORDER_METHOD = 'reorder'
FONT_SIZE = 'fontSize'
THUMB_SIZE = 'thumbSize'
PREFIX_TEXT_COLOR = 'PrefixTextColor'
SUFFIX_TEXT_COLOR = 'SuffixTextColor'

ADDON = Addon()
PLUGIN_ID = int(sys.argv[1])
PLUGIN_URL = sys.argv[0]

# Custom Favourites window class for managing the favourites items.
class CustomFavouritesDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

        # Map control IDs to custom handler methods. You can find the control IDs inside
        # the custom skin XML bundled with this add-on (/resources/skins/Default/1080i/CustomFavouritesDialog[sm lg].XML).
        self.idHandlerDict = {
            101: self.doSelect,
            301: self.close,
            302: self.doReload,
            # 303: self.doConfigure,
            303: self.doSortItems,
            304: self.doPreSuffix,
        }

        # Map action IDs to custom handler methods. See more action IDs in
        # https://github.com/xbmc/xbmc/blob/master/xbmc/input/actions/ActionIDs.h
        self.actionHandlerDict = {
            # All click/select actions are already handled by 'idHandlerDict' above.
            #7: self.doSelect, # ACTION_SELECT_ITEM
            #100: self.doSelect, # ACTION_MOUSE_LEFT_CLICK
            #108: self.doSelect, # ACTION_MOUSE_LONG_CLICK
            9: self.doUnselectClose, # ACTION_PARENT_DIR
            92: self.doUnselectClose, # ACTION_NAV_BACK
            10: self.doUnselectClose, # ACTION_PREVIOUS_MENU
            101: self.doUnselectClose, # ACTION_MOUSE_RIGHT_CLICK
            110: self.doUnselectClose # ACTION_BACKSPACE
        }
        self.noop = lambda: None

    @staticmethod
    def _makeFavourites(favouritesGen):
        LISTITEM = xbmcgui.ListItem
        artDict = {'thumb': None}
        for index, data in enumerate(favouritesGen):
            # The path of each ListItem contains the original favourite entry XML text (with the label, thumb and URL)
            # and this is what's written to the favourites file upon saving -- what changes is the order of the items.
            # add action field to Label2
            li = LISTITEM(data[0], data[3], path=data[2])
            artDict['thumb'] = data[1] # Slightly faster than recreating a dict on every item.
            li.setArt(artDict)

            # TEST - Try modifying prefix for all
            # li.setLabel("##Mike -" + data[0])
            if DEBUG == '1': log_msg = "[COLOR red]Manage Kodi Favourites INFO:[/COLOR] New Label = %s" % data[2]
            if DEBUG == '1': xbmc.log(log_msg, level=xbmc.LOGINFO)

            li.setProperty('thumb', data[4])
            li.setProperty('sortname', data[5])

            li.setProperty('index', str(index)) # To help with resetting, if necessary.
            yield li

    # Function used to start the dialog.
    def doCustomModal(self, favouritesGen):

        if DEBUG3 == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "\n[COLOR red]### WARNING:[/COLOR] Addon under development. Prefix/Suffix and Colors not permanently saved!')
        
        reorderingMethod = '0' if not ADDON.getSetting('reorderingMethod') else ADDON.getSetting('reorderingMethod')
        self.setProperty(REORDER_METHOD, reorderingMethod)
        fontSize = '0' if not ADDON.getSetting('fontSize') else ADDON.getSetting('fontSize')
        self.setProperty(FONT_SIZE, fontSize)
                
        # Determine the Prefix Text from Configuration Settings
        if ADDON.getSetting('prefixTextCus'):
            cur_prefix_text = ADDON.getSetting('prefixTextCus')
        else:
            cur_prefix_text = ADDON.getSetting('prefixTextSel')
            
        # Determine the Prefix Color from Configuration Settings
        if ADDON.getSetting('prefixColorCus'):
            cur_prefix_color = ADDON.getSetting('prefixColorCus')
        else:
            cur_prefix_color = ADDON.getSetting('prefixColSel')

        # Determine the Suffix Text from Configuration Settings
        if ADDON.getSetting('suffixTextCus'):
            cur_suffix_text = ADDON.getSetting('suffixTextCus')
        else:
            cur_suffix_text = ADDON.getSetting('suffixTextSel')
            
        # Determine the Suffix Color from Configuration Settings
        if ADDON.getSetting('suffixColorCus'):
            cur_suffix_color = ADDON.getSetting('suffixColorCus')
        else:
            cur_suffix_color = ADDON.getSetting('suffixColSel')

        PrefixTextColor = '[COLOR yellow]' + cur_prefix_text + ' / ' + cur_prefix_color + '[/COLOR]'
        SuffixTextColor = '[COLOR yellow]' + cur_suffix_text + ' / ' + cur_suffix_color + '[/COLOR]'

        self.setProperty(PREFIX_TEXT_COLOR, PrefixTextColor)
        self.setProperty(SUFFIX_TEXT_COLOR, SuffixTextColor)
     
        if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n(Entry: Prefix Label)' %  str(cur_prefix_text))
        if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n(Entry: Prefix Color)' %  str(cur_prefix_color))
        
        self.allItems = list(self._makeFavourites(favouritesGen))
        self.indexFrom = None # Integer index of the source item (or None when nothing is selected).
        self.isDirty = False # Bool saying if there were any user-made changes at all.

        self.doModal()
        if self.isDirty:
            return self._makeNewResult()
        else:
            return ''

    # Automatically called before the dialog is shown. The UI controls exist now.
    def onInit(self):
        self.panel = self.getControl(101)
        self.panel.reset()
        self.panel.addItems(self.allItems)
        self.setFocusId(100) # Focus the group containing the panel, not the panel itself.
        reorderingMethod = '0' if not ADDON.getSetting('reorderingMethod') else ADDON.getSetting('reorderingMethod')
        setRawWindowProperty(REORDER_METHOD, reorderingMethod)
        thumbSize = '0' if not ADDON.getSetting('thumbSize') else ADDON.getSetting('thumbSize')
        setRawWindowProperty(THUMB_SIZE, thumbSize)

    def onClick(self, controlId):
        self.idHandlerDict.get(controlId, self.noop)()

    def onAction(self, action):
        self.actionHandlerDict.get(action.getId(), self.noop)()

    def doSelect(self):
        selectedPosition = self.panel.getSelectedPosition()
        if self.indexFrom == None:
            # Selecting a new item to reorder.
            self.indexFrom = selectedPosition
            self.panel.getSelectedItem().setProperty('selected', '1')
        else:
            # Something was already selected, so do the reodering.
            if self.indexFrom != selectedPosition:
                self.allItems[self.indexFrom].setProperty('selected', '')

                # Reorder the two distinct items in a specific way:
                reorderingMethod = getRawWindowProperty(REORDER_METHOD)

                # If using the swap mode, or if the items are direct neighbors, then
                # just swap them.
                if reorderingMethod == '0' \
                   or (self.indexFrom == (selectedPosition + 1)) \
                   or (self.indexFrom == (selectedPosition - 1)):
                    # Swap A and B.
                    self.allItems[self.indexFrom], self.allItems[selectedPosition] = (
                        self.allItems[selectedPosition], self.allItems[self.indexFrom]
                    )
                else:
                    itemFrom = self.allItems.pop(self.indexFrom)
                    if reorderingMethod == '1':
                        # Place A behind B.
                        # In case A is at some point BEHIND of B, reduce
                        # one index because popping A caused the list to shrink.
                        if self.indexFrom < selectedPosition:
                            selectedPosition = selectedPosition - 1
                    else:
                        # Place A ahead of B (the original ordering method).
                        # In case A is at some point AHEAD of B, move up
                        # one index because .insert() always puts it behind.
                        if self.indexFrom > selectedPosition:
                            selectedPosition = selectedPosition + 1
                    self.allItems.insert(selectedPosition, itemFrom)

                # Reset the selection state.
                self.isDirty = True
                self.indexFrom = None

                # Commit the changes to the UI, and highlight item A.
                self.panel.reset()
                self.panel.addItems(self.allItems)
                self.panel.selectItem(selectedPosition)
            else: # User reselected the item, so just unmark it.
                self.indexFrom = None
                self.panel.getSelectedItem().setProperty('selected', '')

    def doUnselectClose(self):
        # If there's something selected, unselect it. Otherwise, close the dialog.
        if self.indexFrom != None:
            self.allItems[self.indexFrom].setProperty('selected', '')
            self.indexFrom = None
        else:
            self.close()

    def doConfigure(self):
        if xbmcgui.Dialog().yesno(
            'Manage Kodi Favourites',
            'This will abandon any Prefix/Suffix and Color changes, close this popup and take you to the Configuration Panel.\nProceed?'
        ):
            self.close()
            # Call up Addon Settings
            # Activate the Manage Kodi Favourites Settings window
            xbmc.executebuiltin('Addon.OpenSettings(Manage-Kodi-Favourites)')
  
    def doPreSuffix(self):
        # Check to see if an entry is selected
        if self.indexFrom == None:
            ## Notify User to Select an Item
            xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n\n(Please Select an Item)' % "No Item")
        else:
            if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n\n(Item Selected)' % str(self.indexFrom))

            # Determine the Prefix Text from Configuration Settings
            if ADDON.getSetting('prefixTextCus'):
                cur_prefix_text = ADDON.getSetting('prefixTextCus')
            else:
                cur_prefix_text = ADDON.getSetting('prefixTextSel')
                        
            # Determine the Prefix Color from Configuration Settings
            if ADDON.getSetting('prefixColorCus'):
                cur_prefix_color = ADDON.getSetting('prefixColorCus')
            else:
                cur_prefix_color = ADDON.getSetting('prefixColSel')
    
            # Determine the Suffix Text from Configuration Settings
            if ADDON.getSetting('suffixTextCus'):
                cur_suffix_text = ADDON.getSetting('suffixTextCus')
            else:
                cur_suffix_text = ADDON.getSetting('suffixTextSel')
                
            # Determine the Suffix Color from Configuration Settings
            if ADDON.getSetting('suffixColorCus'):
                cur_suffix_color = ADDON.getSetting('suffixColorCus')
            else:
                cur_suffix_color = ADDON.getSetting('suffixColSel')

            # Now Update the Prefix - Suffix and Color of selected item suffix
            listitem_at_index = self.allItems[self.indexFrom]
            label = listitem_at_index.getLabel()
            if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n(Item Selected)' %  str(label))

            # Ignore NONE entries
            if cur_prefix_text == 'NONE':
                newPrefixText = ''
            else:
                newPrefixText = cur_prefix_text

            if cur_suffix_text == 'NONE':
                newSuffixText = ''
            else:
                newSuffixText = cur_suffix_text 
                
            if cur_prefix_color == 'NONE':
                newPrefixTextColor = newPrefixText
            else:
                newPrefixTextColor = "[COLOR " + cur_prefix_color + "]" + newPrefixText + "[/COLOR]"
            
            if cur_suffix_color == 'NONE':
                newSuffixTextColor = newSuffixText
            else:
                newSuffixTextColor = "[COLOR " + cur_suffix_color + "]" + newSuffixText + "[/COLOR]"
            
            new_label = newPrefixTextColor + label + newSuffixTextColor

            if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n(New Label)' %  str(new_label))

            # Check setting to see if we should let the user know that there are about to modify a List entry
            verbose = 'false' if not ADDON.getSetting('presuffixBool') else ADDON.getSetting('presuffixBool')
                
            # Let the user know that there are about to modify a List entry
            msg_text = f"This will modify the Prefix/Suffix/Color of the currently selected item to:.\n{new_label}\nProceed?"
            if verbose == 'true':
                if xbmcgui.Dialog().yesno('Manage Kodi Favourites', msg_text):
                    # Show the change to the list item
                    listitem_at_index.setLabel(new_label)
            
                    # Mark the change but dont reset the selection state.
                    self.isDirty = True
    
                    # UnSelect the current item
                    self.allItems[self.indexFrom].setProperty('selected', '')
                    self.indexFrom = None
                    self.panel.getSelectedItem().setProperty('selected', '')
            else:
                # Show the change to the list item
                listitem_at_index.setLabel(new_label)
            
                # Mark the change
                self.isDirty = True

                # UnSelect the current item
                self.allItems[self.indexFrom].setProperty('selected', '')
                self.indexFrom = None
                self.panel.getSelectedItem().setProperty('selected', '')

    def doSortItems(self):
        if xbmcgui.Dialog().yesno(
            'Manage Kodi Favourites',
            'This will sort all items in your Favourites list.\nProceed?'
        ):
            
            # Re-sort all items based on their original indices.
            self.indexFrom = None
            self.allItems = sorted(self.allItems, key=lambda li: li.getProperty('sortname'))
            self.panel.reset()
            self.panel.addItems(self.allItems)

            # Mark the change
            self.isDirty = True

    
    def doReload(self):
        if xbmcgui.Dialog().yesno(
            'Manage Kodi Favourites',
            'This will restore the order from the favourites file so you can try reordering again.\nProceed?'
        ):
            
            # Re-sort all items based on their original indices.
            selectedPosition = self.panel.getSelectedPosition()
            self.indexFrom = None
            self.allItems = sorted(self.allItems, key=lambda li: int(li.getProperty('index')))
            self.panel.reset()
            self.panel.addItems(self.allItems)
            if selectedPosition != -1:
                self.panel.selectItem(selectedPosition)


    def _makeResult(self):
        INDENT_STRING = ' ' * 4
        return '<favourites>\n' + '\n'.join((INDENT_STRING + li.getPath()) for li in self.allItems) + '\n</favourites>\n'

    def _makeNewResult(self):
        INDENT_STRING = ' ' * 4
        return '<favourites>\n' + '\n'.join((INDENT_STRING + '<favourite name="' + li.getLabel() + '"thumb="' + li.getProperty('thumb') + '">' + li.getLabel2() + '</favourite>\n') for li in self.allItems) + '\n</favourites>\n'

#===================================================================================

def favouritesDataGen():
    file = xbmcvfs.File(FAVOURITES_PATH)
    contents = DECODE_STRING(file.read())
    file.close()

    namePattern = re.compile('name\s*=\s*"([^"]+)')
    thumbPattern = re.compile('thumb\s*=\s*"([^"]+)')
    actionPattern = re.compile('>\s*([^<]+)')
    sortnamePattern = r"\[\/?COLOR.*?\]"
                               
    for entryMatch in re.finditer('(<favourite\s+[^<]+</favourite>)', contents):
        entry = entryMatch.group(1)

        match = namePattern.search(entry)
        name = PARSER.unescape(match.group(1)) if match else ''
        sortname = re.sub(sortnamePattern, "", name, flags=re.I)

        if DEBUG == '1': log_msg = "[COLOR red]Manage Kodi Favourites INFO:[/COLOR] Sort Name: %s" % sortname
        if DEBUG == '1': xbmc.log(log_msg, level=xbmc.LOGINFO)             
        
        match = thumbPattern.search(entry)
        if match:
            thumb = PARSER.unescape(match.group(1))
            origThumb = thumb
            cacheFilename = xbmc.getCacheThumbName(thumb)
            if 'ffffffff' not in cacheFilename:
                if '.jpg' in thumb:
                    cacheFilename = cacheFilename.replace('.tbn', '.jpg', 1)
                if '.png' in thumb:
                    cacheFilename = cacheFilename.replace('.tbn', '.png', 1)
                thumb = THUMBNAILS_PATH_FORMAT.format(folder=cacheFilename[0], file=cacheFilename)
        else:
            thumb = ''

        match = actionPattern.search(entry)
        action = PARSER.unescape(match.group(1)) if match else ''

        # TEST - Write out the Action field
        if DEBUG == '1': log_msg = "[COLOR red]Manage Kodi Favourites INFO:[/COLOR] Action Field: %s" % action
        if DEBUG == '1': xbmc.log(log_msg, level=xbmc.LOGINFO)     
        
        # Yield a 3-tuple of name, thumb-url and the original content of the favourites entry.
        yield name, thumb, entry, action, origThumb, sortname


def saveFavourites(xmlText):
    if not xmlText:
        return False
    try:
        file = xbmcvfs.File(FAVOURITES_PATH, 'w')
        file.write(xmlText)
        file.close()
    except Exception as e:
        raise Exception('ERROR: unable to write to the Favourites file. Nothing was saved.')
    return True

    if not xmlText:
        return False
    try:
        file = xbmcvfs.File(NEW_FAVOURITES_PATH, 'w')
        file.write(xmlText)
        file.close()
    except Exception as e:
        raise Exception('ERROR: unable to write to the New Favourites file. Nothing was saved.')
    return True


def overwriteFavourites():

    # --- Configuration Variables ---
    # Type of browse dialog: 1 = ShowAndGetFile
    browse_type = 1
    # Dialog heading
    heading = 'Select the favourites.xml file'
    # The starting path. Use "" to list local drives and network shares
    # or specify a default path like 'special://home/addons/'
    default_path = 'special://home' 
    # File mask for readable files (e.g., text, xml, log files). Use '|' to separate extensions.
    file_mask = 'favourite.xml' 
    # Enable multiple file selection (optional)
    enable_multiple = False
    
    # --- Show the browse dialog ---
    dialog = xbmcgui.Dialog()
    selected_file_path = dialog.browse(
        browse_type,
        heading,
        '',  # shares parameter: "" for local/network sources, "files" for file sources
        file_mask,
        enableMultiple=enable_multiple,
        defaultt=default_path # default path to start browsing from
    )

    # Does the selected file include "favourites.xml"
    if "favourites.xml" in selected_file_path:
    
        # --- Process the result ---
        if selected_file_path:
            xbmc.log(f"[COLOR red]Manage Kodi Favourites: [/COLOR]Selected file path: {selected_file_path}", xbmc.LOGINFO)
            # You can now use xbmcvfs to read the file content
            # Example (requires importing xbmcvfs):
            # import xbmcvfs
            # with xbmcvfs.File(selected_file_path, 'r') as f:
            #     content = f.read()
            #     xbmc.log(f"File content snippet: {content[:100]}", xbmc.LOGINFO)
    
            # Define source and destination paths using xbmc.translatePath()
            # 'special://home/' is a common built-in path in Kodi that points to the userdata folder
            src = xbmcvfs.translatePath(selected_file_path)
            dst = xbmcvfs.translatePath(FAVOURITES_PATH)
            
            # Add error handling using a try-except block
            try:
                shutil.copyfile(src, dst)
                # Display a confirmation dialog (requires xbmcgui)
                dialog = xbmcgui.Dialog()
                dialog.ok("File Operation", "[COLOR red]Manage Kodi Favourites: [/COLOR]favourites.xml successfully copied!\n\nYou must restart Kodi or [COLOR orange]Reload Profile[/COLOR]\nto view the change")
            except IOError as e:
                # Display an error dialog if the operation fails
                dialog = xbmcgui.Dialog()
                dialog.ok("File Operation Error", f"[COLOR red]Manage Kodi Favourites: [/COLOR]Error copying favourites.xml file: {e}")
        
        else:
            xbmc.log("[COLOR red]Manage Kodi Favourites: [/COLOR]File selection cancelled by user.", xbmc.LOGINFO)
    else:
        # Display an error dialog if the operation fails
        dialog = xbmcgui.Dialog()
        dialog.ok("File Operation Error", f"[COLOR red]Manage Kodi Favourites: [/COLOR]Invalid Filename: Please select 'favourites.xml'")


def getRawWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    return window.getProperty(prop)


def setRawWindowProperty(prop, data):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    window.setProperty(prop, data)


def clearWindowProperty(prop):
    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    window.clearProperty(prop)


# Debugging helper. Logs a LOGNERROR-level message.
def xbmcLog(*args):
    xbmc.log('[COLOR yellow]Manage Kodi Favourites > [/COLOR]' + ' '.join((var if isinstance(var, str) else repr(var)) for var in args), level=xbmc.LOGERROR)
#===================================================================================

### Entry point ###

if '/dialog' in PLUGIN_URL:
    thumbSize = '0' if not ADDON.getSetting('thumbSize') else ADDON.getSetting('thumbSize')
    if thumbSize == '0':
        if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n(thumSize is SMALL)' % thumbSize)
        ui = CustomFavouritesDialog('CustomFavouritesDialog-smThumbs.xml', ADDON.getAddonInfo('path'), 'Default', '1080i')
    else:
        if DEBUG == '1': xbmcgui.Dialog().ok('Manage Kodi Favourites', 'INFO: "%s"\n(thumSize is LARGE)' % thumbSize)
        ui = CustomFavouritesDialog('CustomFavouritesDialog-lgThumbs.xml', ADDON.getAddonInfo('path'), 'Default', '1080i')
    try:  
        result = ui.doCustomModal(favouritesDataGen())
        setRawWindowProperty(PROPERTY_FAVOURITES_RESULT, result)
    except Exception as e:
        xbmcLog(traceback.format_exc())
        xbmcgui.Dialog().ok('Manage Kodi Favourites Error', 'ERROR: "%s"\n(Please check the log for more info)' % str(e))
        clearWindowProperty(PROPERTY_FAVOURITES_RESULT)
        clearWindowProperty(REORDER_METHOD)
        clearWindowProperty(THUMB_SIZE)
        clearWindowProperty(FONT_SIZE)
        clearWindowProperty(PREFIX_TEXT_COLOR)
        clearWindowProperty(SUFFIX_TEXT_COLOR)

    finally:
        del ui # Delete the dialog instance after it's done, as it's not garbage collected.

elif '/save_reload' in PLUGIN_URL:
    # Reload the current profile (which causes a reload of 'favourites.xml').
    try:
        if saveFavourites(getRawWindowProperty(PROPERTY_FAVOURITES_RESULT)):
            clearWindowProperty(PROPERTY_FAVOURITES_RESULT)
            clearWindowProperty(REORDER_METHOD)
            clearWindowProperty(THUMB_SIZE)
            clearWindowProperty(FONT_SIZE)
            clearWindowProperty(PREFIX_TEXT_COLOR)
            clearWindowProperty(SUFFIX_TEXT_COLOR)
            
            xbmcgui.Dialog().ok('Manage Kodi Favourites', 'Save successful, press OK to reload your Kodi profile\n\nThis may take several seconds...')
            xbmc.executebuiltin('LoadProfile(%s)' % xbmc.getInfoLabel('System.ProfileName'))
            # Alternative way of issuing a profile reload, using JSON-RPC:
            #rpcQuery = (
            #    '{"jsonrpc": "2.0", "id": "1", "method": "Profiles.LoadProfile", "params": {"profile": "%s"}}'
            #    % xbmc.getInfoLabel('System.ProfileName')
            #)
            #xbmc.executeJSONRPC(rpcQuery)
        else:
            # Nothing to save, so just "exit" (go back from) the add-on.
            xbmc.executebuiltin('Action(Back)')
    except Exception as e:
        xbmcLog(traceback.format_exc())
        xbmcgui.Dialog().ok('Manage Kodi Favourites Error', 'ERROR: "%s"\n(Please check the log for more info)' % str(e))

elif '/save_exit' in PLUGIN_URL:
    # Reload the current profile (which causes a reload of 'favourites.xml').
    try:
        if saveFavourites(getRawWindowProperty(PROPERTY_FAVOURITES_RESULT)):
            clearWindowProperty(PROPERTY_FAVOURITES_RESULT)
            clearWindowProperty(REORDER_METHOD)
            clearWindowProperty(THUMB_SIZE)
            clearWindowProperty(FONT_SIZE)
            clearWindowProperty(PREFIX_TEXT_COLOR)
            clearWindowProperty(SUFFIX_TEXT_COLOR)
            xbmcgui.Dialog().ok('Manage Kodi Favourites', 'Save successful. Press OK to exit Manage Kodi Favourites...')
        xbmc.executebuiltin('Action(Back)')
    except Exception as e:
        xbmcLog(traceback.format_exc())
        xbmcgui.Dialog().ok('Manage Kodi Favourites Error', 'ERROR: "%s"\n(Please check the log for more info)' % str(e))

elif '/save_noexit' in PLUGIN_URL:
    # Reload the current profile (which causes a reload of 'favourites.xml').
    try:
        if saveFavourites(getRawWindowProperty(PROPERTY_FAVOURITES_RESULT)):
            xbmcgui.Dialog().ok('Manage Kodi Favourites', 'Save successful. Press OK to Continue Editing Favourites...')
    except Exception as e:
        xbmcLog(traceback.format_exc())
        xbmcgui.Dialog().ok('Manage Kodi Favourites Error', 'ERROR: "%s"\n(Please check the log for more info)' % str(e))

elif '/nosave_reload' in PLUGIN_URL:
    # Reload the current profile (which causes a reload of 'favourites.xml').
    clearWindowProperty(PROPERTY_FAVOURITES_RESULT)
    clearWindowProperty(REORDER_METHOD)
    clearWindowProperty(THUMB_SIZE)
    clearWindowProperty(FONT_SIZE)
    clearWindowProperty(PREFIX_TEXT_COLOR)
    clearWindowProperty(SUFFIX_TEXT_COLOR)
    
    xbmcgui.Dialog().ok('Manage Kodi Favourites', 'Exiting and Reloading Kodi Profile, press OK to start the reload\n\nThis may take several seconds...')
    xbmc.executebuiltin('LoadProfile(%s)' % xbmc.getInfoLabel('System.ProfileName'))

elif '/exit_only' in PLUGIN_URL:
    # Clear the results property and go back one screen (to wherever the user came from).
    clearWindowProperty(PROPERTY_FAVOURITES_RESULT)
    clearWindowProperty(REORDER_METHOD)
    clearWindowProperty(THUMB_SIZE)
    clearWindowProperty(FONT_SIZE)
    clearWindowProperty(PREFIX_TEXT_COLOR)
    clearWindowProperty(SUFFIX_TEXT_COLOR)
    xbmc.executebuiltin('Action(Back)')
    # Alternative action, going to the Home screen.
    #xbmc.executebuiltin('ActivateWindow(home)') # ID taken from https://kodi.wiki/view/Window_IDs

elif '/configure' in PLUGIN_URL:
    # Call up the configuration panel.
    # Activate the Manage Kodi Favourites Settings window
    xbmc.executebuiltin('Addon.OpenSettings(Manage-Kodi-Favourites)')

elif '/overwrite_favs' in PLUGIN_URL:
    # Let the user know that there are about to Overwrite their Favourites file
    verbose = 'false' if not ADDON.getSetting('presuffixBool') else ADDON.getSetting('presuffixBool')

    msg_text = f"[COLOR red]DANGER! [/COLOR]This will overwrite your Kodi Favourites file and cannot be undone - Proceed?"
    if verbose == 'true':
        if xbmcgui.Dialog().yesno('Manage Kodi Favourites', msg_text):
            # Activate the filemaanager
            overwriteFavourites()
    else:
        overwriteFavourites()

else:
    # Create the menu items.
    xbmcplugin.setContent(PLUGIN_ID, 'files')

    dialogItem = xbmcgui.ListItem('[COLOR blue][B]Manage Your Kodi Favourites...[/COLOR](Edit Your Favourites List)[/B]')
    dialogItem.setArt({'thumb': 'DefaultAddonContextItem.png'})
    dialogItem.setInfo('video', {'plot': 'Open the dialog where you can Manage your favourites.[CR][B]How to ' \
                                 'use:[/B] select one item, then select another to Insert/Swap. ' \
                                 'Do this as much as needed. Finally, close the dialog and use the menus ' \
                                 'below to save your changes.'})
    saveReloadItem = xbmcgui.ListItem('   Apply Changes (Save-Exit-Reload Your Kodi Profile)')
    saveReloadItem.setArt({'thumb': 'DefaultAddonsUpdates.png'})
    saveReloadItem.setInfo('video', {'plot': 'Save any changes you made and reload your Kodi profile '
                                       'to make the changes visible right now, without having to restart Kodi.'})
    saveExitItem = xbmcgui.ListItem('   Save & Exit (Save-Exit-No Reload - Leave Changes Pending a Kodi Restart or [COLOR orange]Reload Profile[/COLOR])')
    saveExitItem.setArt({'thumb': 'DefaultAddonsUpdates.png'})
    saveExitItem.setInfo('video', {'plot': 'Save any changes you made and exit the add-on. [B]Note:[/B] if you '
                                   'make any changes to your favourites using the Favourites screen (like adding, '
                                   'removing or reordering items) before closing Kodi, your changes from this '
                                   'add-on will be ignored.'})
    saveSaveItem = xbmcgui.ListItem('   Save Only (Save-No Exit-No Reload - Leave Changes Pending a Kodi Restart or [COLOR orange]Reload Profile[/COLOR])')
    saveSaveItem.setArt({'thumb': 'DefaultFolderBack.png'})
    saveSaveItem.setInfo('video', {'plot': 'Save any changes you made but do not exit the add-on. [B]Note:[/B] if you '
                                   'make any changes to your favourites using the Favourites screen (like adding, '
                                   'removing or reordering items) before closing Kodi, your changes from this '
                                   'add-on will be ignored.'})
    nosaveReloadItem = xbmcgui.ListItem('   Exit & [COLOR orange]Reload Profile[/COLOR] Only (No Save-Exit-Reload Your Kodi Profile)')
    nosaveReloadItem.setArt({'thumb': 'DefaultAddonsUpdates.png'})
    nosaveReloadItem.setInfo('video', {'plot': 'Do not save any changes you made, exit the add-on and Reload you Kodi profile. [B]Note:[/B] if you '
                                   'make any changes to your favourites using the Favourites screen (like adding, '
                                   'removing or reordering items) before closing Kodi, your changes from this '
                                   'add-on will be ignored.'})
    configureItem = xbmcgui.ListItem('[B]Configure... (Change Settings)[/B]')
    configureItem.setArt({'thumb': 'DefaultFolderBack.png'})
    configureItem.setInfo('video', {'plot': 'Configure the default actions in Settings panel for Prefix, Suffix, Colors and Insert/Swap modes.'})
    overwriteFavs = xbmcgui.ListItem('[COLOR red][B]Overwrite Favourites [/COLOR](Advanced! - Overwrite Fvourites file - Leave Changes Pending a Kodi Restart or [COLOR orange]Reload Profile[/COLOR])[/B]')
    overwriteFavs.setArt({'thumb': 'DefaultFolderBack.png'})
    overwriteFavs.setInfo('video', {'plot': 'Advanced - Overwrite Kodi Favourites file, Leave Changes Pending a Kodi Restart or [COLOR orange]Reload Profile.[/COLOR]'})
    exitItem = xbmcgui.ListItem('[B]Exit (No Save-Exit - Abandon Any Unsaved Changes)[/B]')
    exitItem.setArt({'thumb': 'DefaultFolderBack.png'})
    exitItem.setInfo('video', {'plot': 'Exit the add-on (same as pressing Back), without saving your changes.'})

    xbmcplugin.addDirectoryItems(
        PLUGIN_ID,
        (
            # PLUGIN_URL already ends with a slash, so just append the route to it.
            (PLUGIN_URL + 'dialog', dialogItem, False),
            (PLUGIN_URL + 'save_reload', saveReloadItem, False),
            (PLUGIN_URL + 'save_exit', saveExitItem, False),
            (PLUGIN_URL + 'save_noexit', saveSaveItem, False),
            (PLUGIN_URL + 'nosave_reload', nosaveReloadItem, False),
            (PLUGIN_URL + 'configure', configureItem, False),
            (PLUGIN_URL + 'overwrite_favs', overwriteFavs, False),
            (PLUGIN_URL + 'exit_only', exitItem, False)
        )
    )
    xbmcplugin.endOfDirectory(PLUGIN_ID)







