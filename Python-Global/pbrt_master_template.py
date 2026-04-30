import os

def create_scene_with_metadata(project_path, scene_name, geometry_block):
    """
    Standardizes pbrt-v4 scene generation with Adobe-friendly metadata.
    """
    pbrt_filename = f"{scene_name}.pbrt"
    xmp_filename = f"{scene_name}.xmp"
    
    # 1. The Core PBRT-v4 Header (Your 'Standard' look)
    header = f"""
LookAt 3 4 12  0 0 0  0 1 0
Camera "perspective" "float fov" [35]
Sampler "zsobol" "integer pixelsamples" [64]
Integrator "volpath"
Film "rgb" "string filename" "../renders/{scene_name}.png"
    "integer xresolution" [1280] "integer yresolution" [720]

WorldBegin
    # 6500K Daylight Setup
    LightSource "infinite" "rgb L" [0.6 0.7 1.0]
    LightSource "distant" "point3 from" [10 10 10] "rgb L" [5 5 5]
"""

    # 2. The Metadata 'DNA' (For Adobe Bridge/Photoshop)
    xmp_content = f"""<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:description>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">
     SOURCE: {scene_name}.py
     CALIBRATION: 6500K
     GEOMETRY: Procedural Lattice v1.0
     </rdf:li>
    </rdf:Alt>
   </dc:description>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

    # 3. Write Files
    with open(os.path.join(project_path, "scenes", pbrt_filename), "w") as f:
        f.write(header + geometry_block)
        
    with open(os.path.join(project_path, "renders", xmp_filename), "w") as f:
        f.write(xmp_content)

    print(f"Success: Scene and Metadata generated for {scene_name}")