import zipfile
import os
import toml

# Read config
config = toml.load(os.path.join(os.path.dirname(__file__), "config.toml"))
homework_dir = config.get("homework_dir", "hw0")
submissions_dir = config.get("submissions_dir", "submissions")

zip_path = os.path.join(homework_dir, "submissions.zip")
output_dir = os.path.join(homework_dir, submissions_dir)
os.makedirs(output_dir, exist_ok=True)

with zipfile.ZipFile(zip_path, 'r') as zipf:
    for name in zipf.namelist():
        if name.endswith('.ipynb'):
            # Extract user_id between 2nd and 3rd underscore
            parts = name.split('_')
            user_id = ""
            if parts[1] == "LATE":
                user_id = parts[2]
            else:
                user_id = parts[1]
            new_name = f"{user_id}.ipynb"
            data = zipf.read(name)
            with open(os.path.join(output_dir, new_name), 'wb') as f:
                f.write(data)
