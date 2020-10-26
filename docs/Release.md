# How to release

This is documenting the release process.


## Git flow & CHANGELOG.md

Make sure the CHANGELOG.md is up to date and follows the http://keepachangelog.com guidelines.
Start the release with git flow:
```sh
git flow release start YYYYMMDD
```
Now update the [CHANGELOG.md](/CHANGELOG.md) `[Unreleased]` section to match the new release version.
Also update the `version` string in the [setup.py](/setup.py) file. Then commit and finish release.
```sh
git commit -a -m ":bookmark: YYYYMMDD"
git flow release finish
```
Push everything, make sure tags are also pushed:
```sh
git push
git push origin master:master
git push --tags
```

## Publish to PyPI
This process is handled automatically by Travis.
If needed below are the instructions to perform it manually.
Build it:
```sh
make release/build
```
Check archive content:
```sh
tar -tvf dist/pools-*.tar.gz
```
Upload:
```sh
make release/upload
```

## GitHub

Got to GitHub [Release/Tags](https://github.com/AndreMiras/libpools/tags), click "Add release notes" for the tag just created.
Add the tag name in the "Release title" field and the relevant CHANGELOG.md section in the "Describe this release" textarea field.
Finally, attach the generated APK release file and click "Publish release".
