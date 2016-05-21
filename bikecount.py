from qgis.core import *
import ipdb


# supply path to qgis install location
QgsApplication.setPrefixPath("C:/OSGeo4W64", True)

# create a reference to the QgsApplication, setting the
# second argument to False disables the GUI
qgs = QgsApplication([], False)

# load providers
qgs.initQgis()

# Write your code here to load some layers, use processing algorithms, etc.

ipdb.set_trace()

# When your script is complete, call exitQgis() to remove the provider and
# layer registries from memory
qgs.exitQgis()
