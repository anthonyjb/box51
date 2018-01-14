Box51
=====

An image processing library created for manhattan to allow local file storage
without running an instance of hangar51.


Installation
------------

`pip install box51`


Manhattan setup
---------------

Modify you application config as follows:

    from manhattan.assets.backends import box51
    from werkzeug.contrib.cache import SimpleCache

    class Config:

        # Assets
        ASSET_BACKEND = box51
        ASSET_BACKEND_SETTINGS = {
            'asset_dir': '/path/to/assets',
            'cache': SimpleCache()
        }
        ASSET_BACKEND_ROOT = '/assets'