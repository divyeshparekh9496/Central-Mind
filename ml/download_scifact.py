"""Download BEIR's SciFact format; preserve upstream attribution and archive hash."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

URL = 'https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip'


def main():
    destination = Path('data')
    destination.mkdir(exist_ok=True)
    archive = destination/'scifact.zip'
    if not archive.exists():
        urllib.request.urlretrieve(URL,archive)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            target = (destination/name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Invalid archive member')
        z.extractall(destination)
    (destination/'scifact-provenance.json').write_text(json.dumps({
        'url':URL,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'upstream':'https://github.com/allenai/scifact',
        'license':'Claims: CC BY 4.0; abstracts: ODC-By 1.0; see upstream LICENSE.md',
    },indent=2)+'\n')
    print('Downloaded data/scifact; raw corpus remains git-ignored.')


if __name__ == '__main__':
    main()
