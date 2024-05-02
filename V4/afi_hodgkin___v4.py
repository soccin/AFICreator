import sys
import os
import re
from string import Template

markerPattern=re.compile("^([^_]+)_.*_spot_(\d+).tif$")
dapiPattern=re.compile("^S([^_]+)_.*_spot_(\d+).tif$")

imageTmpl=Template("""<Image>
    <Path>$fileName</Path>
    <BitDepth>16</BitDepth>
    <ChannelName>$marker</ChannelName>
</Image>""")

ofps=dict()

def printImage(sample,spot,marker,fileName):
    outFile="%s_Spot%s.afi" % (sample,str(int(spot)))
    if not outFile in ofps:
        ofps[outFile]=open(outFile,"w")
        print("<ImageList>",file=ofps[outFile])
        print("Opening file for",sample,spot)

    print(imageTmpl.substitute(dict(marker=marker,fileName=fileName)),file=ofps[outFile])


if __name__=="__main__":
    start_dir=sys.argv[1]
    for dirpath, dirs, files in os.walk(start_dir):
        if files:
            for ff in files:
                fullPath=os.path.abspath(dirpath)
                sample=fullPath.split("/")[-1]
                if ff.find("dapi")>-1 or ff.find("DAPI")>-1:
                    mm=dapiPattern.search(ff)
                    cycle=mm.group(1)
                    spot=mm.group(2)
                    marker="DAPI"+str(int(cycle))
                else:
                    mm=markerPattern.search(ff)
                    marker=mm.group(1)
                    spot=mm.group(2)

                printImage(sample,spot,marker,ff)

    for fp in ofps:
        print("closing file",fp)
        print("</ImageList>",file=ofps[fp])

