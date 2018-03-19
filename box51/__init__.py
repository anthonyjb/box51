import io
import os

from PIL import Image
from PIL.ExifTags import TAGS
import shortuuid
from slugify import Slugify

__all__ = [
    'Box51',
    'Box51Exception'
]


# Exceptions

class Box51Exception(Exception):
    """An exception performing an action against an asset"""


# API

class Box51:
    """
    The `Box51` class provides an API for the library. After initializing the
    class the new instance can be used to manage assets.
    """

    # The length of key used when saving assets
    KEY_LENGTH = 6

    # The supported image formats (in and out)
    SUPPORTED_IMAGE_EXT = {
        'in': [
            'bmp',
            'gif',
            'jpg', 'jpeg',
            'png',
            'tif', 'tiff',
            'webp'
            ],
        'out': ['jpg', 'gif', 'png', 'webp']
    }

    # The name of the folder in which temporary files are stored
    TMP_DIR = 'tmp'

    def __init__(self, asset_root):

        # Path to the directory where assets will be stored
        self.asset_root = asset_root

        # Create a slugify function for normalizing file names
        self._slugify = Slugify()
        self._slugify.to_lower = True
        self._slugify.safe_chars = '-'
        self._slugify.max_length = 200

    def generate_variations(self, store_key, variations):
        """Generate one or more variations for an image asset"""

        abs_path = self.asset_root
        abs_path_tmp = os.path.join(self.asset_root, self.TMP_DIR)

        # Extract the extension from the store key to create a base key
        base_key = os.path.splitext(store_key)[0]

        # Get the path to the asset
        file_path, temporary = self._get(store_key)

        # Generate the variations
        im = Image.open(file_path)

        new_variations = {}
        for name, ops in variations.items():

            vim = None
            if im.format.lower() == 'gif' and im.is_animated:
                # By-pass transforms for animated gifs
                file = open(file_path, 'rb')
                fmt = {'ext': 'gif', 'fmt': 'gif'}

            else:
                # Transform the image based on the variation
                vim = im.copy()
                vim, fmt = self._transform_image(vim, ops)

                # Convert the image to a stream for saving
                file = io.BytesIO()
                vim.save(file, **fmt)
                file.seek(0)

            # Write the variation to disk
            var_key = None

            while True:

                # Create a unique Id for the asset variation
                uid = self._generate_uid(self.KEY_LENGTH)
                var_key = '.'.join([base_key, name, uid, fmt['ext']])

                # Check the variation key is unique
                if os.path.exists(os.path.join(abs_path, var_key)):
                    continue

                if os.path.exists(os.path.join(abs_path_tmp, var_key)):
                    continue

                # Write the asset to disk
                path = abs_path_tmp if temporary else abs_path
                with open(os.path.join(path, var_key), 'wb') as store:
                    store.write(file.read())

                break

            # Build the variation data
            new_variations[name] = {
                'name': name,
                'store_key': var_key,
                'ext': fmt['ext'],
                'meta': {
                    'length': self._get_file_length(file),
                    'image': {
                        'mode': (vim or im).mode,
                        'size': (vim or im).size
                    }
                }
            }

        return new_variations

    def make_permanent(self, store_key):
        """Move an asset from the temporary folder to the root folder"""

        # Check the file isn't already store in the permanent folder
        abs_path = self.asset_root
        if os.path.exists(os.path.join(abs_path, store_key)):
            return

        # Move the temporary version of the file and any variations
        abs_path_tmp = os.path.join(self.asset_root, self.TMP_DIR)

        # Extract the extension from the store key to create a base key
        base_key = os.path.splitext(store_key)[0]

        # Move the asset and any variations from the temporary folder to the
        # asset root and build a map of the change in filenames from temporary
        # to permenant.
        filename_remap = {}
        for filename in os.listdir(abs_path_tmp):
            if filename.startswith(base_key):

                # Store the key change
                tmp_key = os.path.join(self.TMP_DIR, filename)
                filename_remap[tmp_key] = filename

                # Move the file
                os.rename(
                    os.path.join(abs_path_tmp, filename),
                    os.path.join(abs_path, filename)
                )

        return filename_remap

    def remove(self, store_key):
        """Remove an asset"""
        if os.path.exists(os.path.join(self.asset_root, store_key)):

            # Remove the asset and any variations of it
            for filename in os.listdir(abs_path_tmp):
                if filename.startswith(base_key):
                    os.remove(os.path.join(self.asset_root, filename))

    def retrieve(self, store_key):
        """Retreive an asset"""

        # Get the path to the asset
        abs_path, temporary = self._get(store_key)
        if abs_path == None:
            return

        # Read the asset's contents
        with open(abs_path, 'rb') as file:
            stream = io.BytesIO(file.read())

        return stream

    def store(self, file, name=None, temporary=False):
        """Store an asset"""

        # If no name has been provided attempt to extract one from the file
        if not name:
            name = os.path.splitext(file.filename)[0]

        # Normalize the name
        name = self._slugify(name)

        # Get the file's extension
        ext = os.path.splitext(file.filename)[1].lower()[1:]

        # If we weren't able to get file's extension then attempt to guess it
        if not ext:
            file.stream.seek(0)
            ext = imghdr.what(file.filename, file.stream.read()) or ''

        # Build the meta data for the asset (and strip any meta information
        # from images).
        asset_file = file.stream
        asset_meta = {}
        asset_type = self._get_type(ext)
        if asset_type is 'image':
            asset_file, asset_meta = self._prep_image(asset_file)

        asset_meta.update({
            'filename': file.filename,
            'length': self._get_file_length(asset_file)
        })

        # Determine the storage location
        abs_path = self.asset_root
        abs_path_tmp = os.path.join(self.asset_root, self.TMP_DIR)

        # Ensure the location exists
        os.makedirs(abs_path, exist_ok=True)
        os.makedirs(abs_path_tmp, exist_ok=True)

        # Save the asset
        store_key = None

        while True:

            # Create a unique Id for the asset
            uid = self._generate_uid(self.KEY_LENGTH)
            store_key = '.'.join([name, uid, ext])

            # Check the store key is unique
            if os.path.exists(os.path.join(abs_path, store_key)):
                continue

            if os.path.exists(os.path.join(abs_path_tmp, store_key)):
                continue

            # Write the asset to disk
            path = abs_path_tmp if temporary else abs_path
            with open(os.path.join(path, store_key), 'wb') as store:
                store.write(asset_file.read())

            break

        return {
            'ext': ext,
            'meta': asset_meta,
            'name': name,
            'store_key': store_key,
            'temporary': temporary,
            'type': asset_type,
            'variations': []
        }

    # Private methods

    def _get(self, store_key):
        """
        Return a path to the asset and a flag indicating if it is stored in
        the temporary folder.
        """

        # Find the asset
        asset = None
        temporary = False

        # Check the asset root
        if os.path.exists(os.path.join(self.asset_root, store_key)):
            return os.path.join(self.asset_root, store_key), False

        # Check temporary folder
        abs_path_tmp = os.path.join(self.asset_root, self.TMP_DIR)
        if os.path.exists(os.path.join(abs_path_tmp, store_key)):
            return os.path.join(abs_path_tmp, store_key), True

        return None, None

    @classmethod
    def _get_file_length(cls, file):
        """Return the length of a file"""
        file.seek(0, os.SEEK_END)
        length = file.tell()
        file.seek(0)
        return length

    @classmethod
    def _get_type(cls, ext):
        """Return the type of asset based on the given file extension"""
        if ext.lower() in cls.SUPPORTED_IMAGE_EXT['in']:
            return 'image'
        return 'file'

    @classmethod
    def _generate_uid(cls, length):
        """Generate a uid of the given length"""
        su = shortuuid.ShortUUID(
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789'
        )
        return su.uuid()[:length]

    @classmethod
    def _prep_image(cls, file):
        """Prepare an image file"""

        # Load the image
        im = Image.open(file)
        fmt = im.format

        # Orient the image
        if hasattr(im, '_getexif') and im._getexif():
            # Only JPEG images contain the _getexif tag, however if it's
            # present ww can use it make sure the image is correctly
            # orientated.

            # Convert the exif data to a dictionary with alphanumeric keys
            exif = {TAGS[k]: v for k, v in im._getexif().items() if k in TAGS}

            # Check for an orientation setting and orient the image if required
            orientation = exif.get('Orientation')
            if orientation == 2:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)

            elif orientation == 3:
                im = im.transpose(Image.ROTATE_180)

            elif orientation == 4:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)

            elif orientation == 5:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
                im = im.transpose(Image.ROTATE_90)

            elif orientation == 6:
                im = im.transpose(Image.ROTATE_270)

            elif orientation == 7:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
                im = im.transpose(Image.ROTATE_90)

            elif orientation == 8:
                im = im.transpose(Image.ROTATE_90)

        # Strip meta data from file
        im_no_exif = None
        if im.format == 'GIF':
            im_no_exif = im
        else:
            file = io.BytesIO()
            im_no_exif = Image.new(im.mode, im.size)
            im_no_exif.putdata(list(im.getdata()))
            im_no_exif.save(file, format=fmt)

        file.seek(0)

        # Build base meta information for the image
        meta = {
            'image': {
                'mode': im_no_exif.mode,
                'size': im_no_exif.size
            }
        }

        return file, meta

    @classmethod
    def _transform_image(cls, im, ops):
        """
        Perform a list of operations against an image and return the resulting
        image.
        """

        # Perform the operations
        fmt = {'format': 'jpeg', 'ext': 'jpg'}
        for op in ops:

            # Crop
            if op[0] == 'crop':
                im = im.crop([
                    int(op[1][3] * im.size[0]), # Left
                    int(op[1][0] * im.size[1]), # Top
                    int(op[1][1] * im.size[0]), # Right
                    int(op[1][2] * im.size[1])  # Bottom
                ])

            # Fit
            elif op[0] == 'fit':
                im.thumbnail(op[1], Image.ANTIALIAS)

            # Rotate
            elif op[0] == 'rotate':
                if op[1] == 90:
                    im = im.transpose(Image.ROTATE_270)

                elif op[1] == 180:
                    im = im.transpose(Image.ROTATE_180)

                elif op[1] == 270:
                    im = im.transpose(Image.ROTATE_90)

            # Output
            elif op[0] == 'output':
                fmt = op[1]

                # Set the extension for the output and the format required by
                # Pillow.
                fmt['ext'] = fmt['format']
                if fmt['format'] == 'jpg':
                    fmt['format'] = 'jpeg'

                # Add the optimize flag for JPEGs and PNGs
                if fmt['format'] in ['jpeg', 'png']:
                    fmt['optimize'] = True

                # Allow gifs to store multiple frames
                if fmt['format'] in ['gif', 'webp']:
                    fmt['save_all'] = True
                    fmt['optimize'] = True

        # Variations are output in web safe colour modes, if the
        # original image isn't using a web safe colour mode supported by
        # the output format it will be converted to one.
        if fmt['format'] == 'gif' and im.mode != 'P':
            im = im.convert('P')

        elif fmt['format'] == 'jpeg' and im.mode != 'RGB':
            im = im.convert('RGB')

        elif fmt['format'] == 'png' \
                and im.mode not in ['P', 'RGB', 'RGBA']:
            im = im.convert('RGB')

        elif fmt['format'] == 'webp' and im.mode != 'RGBA':
            im = im.convert('RGBA')

        return im, fmt
