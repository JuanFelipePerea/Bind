from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ManifestStorage(ManifestStaticFilesStorage):
    # Django 6.0 admin base.css references icon-debug.svg; during the
    # post-process URL-rewriting pass the hash lookup fails and Django's
    # ManifestStaticFilesStorage yields a ValueError as `processed`.
    # Django 6.0's collectstatic command re-raises any yielded exception
    # (line 157), so manifest_strict=False alone is not enough.
    # We override post_process to simply drop exception results so
    # collectstatic never sees them.
    manifest_strict = False

    def post_process(self, *args, **kwargs):
        for name, hashed_name, processed in super().post_process(*args, **kwargs):
            if not isinstance(processed, Exception):
                yield name, hashed_name, processed
