''' researchers don't like manually importing tiff files (even if in batch)
    and naming tiff channels individually. This program traverses a given directory
    to generate .afi HALO objects whenever stacks of tif files (organized into spots) appear.
'''


# for the same spot, stack alll the AFRemoved marker tif, and the first and last cycle of dapi tif in registeredImage




import os
import re
import xml.etree.cElementTree as ET
try:
    from tkinter import *
except ImportError:
    from Tkinter import *
from tkinter import filedialog

#
# This needs to match the filename of the image file name, directory names it not 
# important
# 

#
# Group (1) ==> SAMPLE_NAME (L_001, ABTC_014)
# Group (2) ==> Cycle (int)
# Group (3) ==> SPOT (int)
# Group (4) ==> Marker (CD3, DAPI)
#

ge_file_pattern = re.compile(r'^([A-Za-z].+[^_])_(\d+)\.\d+.\d+_R(\d+)_(\S+)_\d+bit_.*\.tif$', re.IGNORECASE)


def path_exists(path):
    return os.path.isdir(path)

def update_usr(listbox, text = '', end = False ):
    if end:
        listbox.insert(END, '    ' + text)
        listbox.insert(END, ' ')
    else:
        listbox.insert(0, '    ' + text)
        listbox.insert(0, ' ')

def collect_spots(path):
    # collect filenames at this path by spot
    spot_dict = dict()
    all_files = next(os.walk(path))[2]
    for f in all_files:
        m = ge_file_pattern.search(f)
        if m:
            #print(m.group(1)) # slide
            #print(m.group(2)) # cycle
            #print(m.group(3)) # fov
            #print(m.group(4)) # marker
            spot = m.group(3)
            if spot in spot_dict.keys():
                spot_dict[spot].append(f)
            else:
                spot_dict[spot] = [f]
    return spot_dict

def channel_name(file_name):
    m = ge_file_pattern.search(file_name)

    if 'dapi' in m.group(4).lower():
        try:
            return 'DAPI%s'%( int(m.group(2)) )
        except ValueError:
            update_usr(listbox, '!!!!!!!!!!!!!!!!!')
            update_usr(listbox, 'bad dapi filename, no cycle number found')
            update_usr(listbox, '!!!!!!!!!!!!!!!!!')

    #if 'AFRemoved' in filename_as_list:
    #    return '_'.join(filename_as_list[ : filename_as_list.index('AFRemoved') ])

    #else:
    return m.group(4)


def write_afi(dirpath, mask_dir, spot, tif_ledger):
    ''' Given where to write, which spot it is writing for
        and ledger (so it can look up filenames), conjugates the filename
        then populates a .afi file, writing to dir
        @param str dirpath: user input passed through traverse from GUI
        @param str mask_dir: user input
        @param str spot: within a dir, each afi corresponds to a spot, which
        links a group of TIF
        @param dic tif_ledeger: keys of this dic are spots, provides a list of filenames
        which belong to this spot
    '''
    #def _case_name(path):
    #    parent_dir = path.split('/')[-2]
    #    return parent_dir

    # read S[year num]_[5 digit serial]_Spot[spot num]

    m = ge_file_pattern.search(tif_ledger[spot][0])

    try:
        filename = '%s_Spot%s.afi' % ( m.group(1),  int(m.group(3)))
    except ValueError:
        update_usr(listbox, '!!!!!!!!!!!!!!!!!')
        update_usr(listbox, 'first tif in this spot is %s' %(tif_ledger[spot][0]))
        update_usr(listbox, 'bad .tif filename, maybe a tif spot is not a number?')
        update_usr(listbox, '!!!!!!!!!!!!!!!!!')

    root = ET.Element("ImageList")
    if mask_dir:
        path_to_write = mask_dir
    else:
        path_to_write = dirpath

    # next code block to sort channel names alphabetically, since S001-> DAPI1
    # create channel names linked w/ tif_name, sort array,
    channel_names_to_sort = []
    unique_channels = []
    for tif_name in tif_ledger[spot]:
        channel_names_to_sort.append( [channel_name(tif_name), tif_name] )
        unique_channels.append(channel_name(tif_name))

    if len(channel_names_to_sort) != len(set(unique_channels)):
        update_usr(listbox, '!!!!!!!!!!!!!!!!!')
        update_usr(listbox, 'files with duplicate channel names at %s, skipped! ' %(dirpath) )
        update_usr(listbox, '!!!!!!!!!!!!!!!!!')
        return False

    channel_names_to_sort.sort(key=lambda x: x[0])

    for c_name_and_tif_name in channel_names_to_sort:

        c_name, tif_name = c_name_and_tif_name
        image_child = ET.SubElement(root, "Image")

        path_child = ET.SubElement(
        image_child, "Path").text = os.path.join(tif_name)

        bitdepth_child = ET.SubElement(
        image_child, "BitDepth").text = "16"

        channelname_child = ET.SubElement(
        image_child, "ChannelName").text = c_name

    tree = ET.ElementTree(root)
    tree.write(os.path.join(path_to_write, filename))


def traverse(start_dir, mask_dir, num_stains):
    ''' traverses all subdir of start_dir, creates a tif_ledger if .tif found
        writes .afi for each spot found at dirpath to dirpath
        (e.g. PR_Spot4_1.afi, PR_Spot2_1.afi at D:/PR_1/AFRemoved/ )
        @param str start_dir: GUI field 1, actual path leading to TIF files
        @param None or str output_dir: GUI field 2, path of another machine to embed into afi
        @param None or str num_stains: GUI field 3, prints warning if spot does not contain this many files
        @return dic tif_ledger: an empty tif_ledger indicates no TIF were found
    '''

    for dirpath, dirs, files in os.walk(start_dir):
        #dirpath = os.path.join(dirpath, '')
        tif_ledger = collect_spots(dirpath)
        for spot in tif_ledger.keys():
                if num_stains and len(tif_ledger[spot]) != int(num_stains):
                    update_usr(listbox, '!!!!!!!!!!!!!!!!!')
                    update_usr(listbox, 'Spot %s at %s has %s .tif files, no .afi written' %(spot, dirpath, len(tif_ledger[spot])))
                    update_usr(listbox, '!! no .afi written !!' )
                    continue
                if  not num_stains:
                    update_usr(listbox, 'Spot %s at %s has %s .tif files' %(spot, dirpath, len(tif_ledger[spot])))

                write_afi(dirpath, mask_dir, spot, tif_ledger)
    #return tif_ledger

def show_entry_fields(listbox):
    ''' calls afi writing functions according to user input into GUI
        traverse( ) takes all user inputs and executes the task, also serves as boolean
        in case directory does not contain any .tif
    '''
    update_usr(listbox, '_______________________________________')
    #path = os.path.join(e1.get(), '')
    input_path = input_path_entry.get()
    input_path_list = input_path.split(',')
    invalid_input_path = False
    for path in input_path_list:
        if not path_exists(path):
            invalid_input_path = True
            update_usr(listbox, 'Input path does not exist: %s' % (path))
    if invalid_input_path:        
        return

    output_path = output_path_entry.get()
    if not output_path:
        update_usr(listbox, 'Output path not provided, afi files will be written to each local directories of linked tif file')
    elif not path_exists(output_path):
        update_usr(listbox, 'Output path does not exist: %s' % (output_path))
        return

    num_stains = (stain_entry.get())
    if num_stains and not num_stains.isdigit():
        update_usr(listbox, 'Number of Stains not an integer')
        return

   # file written by link after calling it, link also a bool indicating if tiff found at path
    for path in input_path_list:
        traverse(path, output_path, num_stains)
        #if not traverse(path, output_path, num_stains):
            #update_usr(listbox, 'No .tif or .tiff found anywhere in %s' %(path))
            #return

def add_path(cur_entry):
    new_dir = filedialog.askdirectory()
    if not new_dir:
        return
    if cur_entry.get():
        cur_entry.insert(END, ",")
    cur_entry.insert(END, new_dir)
    update_usr(listbox, 'Added input dir %s' % (new_dir))

def select_path(cur_entry):
    new_dir = filedialog.askdirectory()
    if not new_dir:
        return
    cur_entry.delete(0, END)
    cur_entry.insert(0, new_dir)
    update_usr(listbox, 'Set output dir to %s' % (cur_entry.get()))









master = Tk()
master.geometry('1200x800+300+300')
master.title("HALO TIFF Linker")
master.lift()
master.attributes('-topmost',True)
master.after_idle(master.attributes,'-topmost',False)
master.rowconfigure(0, minsize=40)
master.rowconfigure(1, minsize=40)
master.rowconfigure(2, minsize=40)
master.rowconfigure(3, minsize=40)
master.rowconfigure(3, minsize=40)
master.columnconfigure(0, minsize=30)
master.columnconfigure(1, minsize=80)
master.columnconfigure(2, minsize=30)


# three user input fields
# input_path, output_path and number of stains for this study
input_label = Label(master, text="Input Directories")
input_label.grid(row=0, column=0)
input_label.config(font=('Helvetica',15))
input_path_entry = Entry(master, width=60)
input_path_entry.grid(row=0, column=1)
Button(master, text='Add Path', command= lambda: add_path(input_path_entry)).grid(row=0, column=2)


output_label = Label(master, text="Output Directory")
output_label.grid(row=1, column=0)
output_label.config(font=('Helvetica',15))
output_path_entry = Entry(master, width = 60)
output_path_entry.grid(row = 1, column = 1)
Button(master, text='Select Path', command= lambda: select_path(output_path_entry)).grid(row=1, column=2)


stain_label = Label(master, text="Number of stains")
stain_label.grid(row=2, column=0)
stain_label.config(font=('Helvetica',15))
stain_entry = Entry(master, width = 10)
stain_entry.grid(row = 2, column = 1)

Button(master, text='Link', command= lambda: show_entry_fields(listbox)).grid(row=3, column=2)
Button(master, text='Quit', command=master.destroy).grid(row=3, column=0)




w = Canvas(master, width = 120, height=15)
w.grid(row=4, column=0, columnspan=3, padx=50)

status = StringVar()
f = Label(w, textvariable=status)

scrollbar = Scrollbar(w)
scrollbar.pack(side=RIGHT, fill=Y)

listbox = Listbox(w, width = 120, height = 30)
listbox.pack()
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox.yview)


update_usr(listbox, '', True)
update_usr(listbox, '________General Notes________', True)
update_usr(listbox, 'all subdirectories from the path provided are traversed and searched', True)
update_usr(listbox, 'THIS PROGRAM WILL RE-WRITE EXISTING AFI IF THEY ARE FOUND W/ SAME NAMING SCHEME IN A SUBDIRECTORY', True)
update_usr(listbox, '''If output dir is not specified, afi linking files are written to where linked TIFFs are''', True)
update_usr(listbox, 'In a directory, TIFFs belonging to the same spot are linked', True)

update_usr(listbox, '________Num of Stains________', True)
update_usr(listbox, """Warnings are printed if .tif files for one spot do not contain""", True)
update_usr(listbox, 'designated number of stains (leave blank for no warning)', True)

mainloop( )
