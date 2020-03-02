import yaml

from other.config import _ as _dict

# with open('config.json', 'r') as f:
#     _dict = json.load(f)
#     print("successfully read data")

with open('../other/config.yaml', 'w') as f:
    yaml.dump(_dict, f)
    print("successfully dumped data")

print("done")
