import sys
import pathlib

# Add dong_converter/ to sys.path so that tests can use bare imports:
#   import config
#   import pipeline_a.geojson_loader as geojson_loader
sys.path.insert(0, str(pathlib.Path(__file__).parent))
