"""Join native TextureID/BoundsIndex pairs to pinned normalized frame identities."""


def frames(library, sequence, texture_id, cell_id):
    found = [fid for fid, frame in library['sequences'][sequence]['frames'].items()
             if frame.get('facing') == 'right'
             and frame.get('provenance', {}).get('texture_id') == texture_id
             and frame.get('provenance', {}).get('cell_id') == cell_id]
    if not found:
        raise ValueError(f'{sequence}: no normalized identity for {texture_id:#x}/{cell_id}')
    return found
