# Ainur

Workload deployment and orchestration on the ExPECA Testbed.

From [Wikipedia](https://en.wikipedia.org/wiki/Ainur_(Middle-earth)):

> The Ainur (singular: Ainu) are the immortal spirits existing before Creation in J. R. R. Tolkien's fictional universe.
> These were the first beings made of the thought of Eru Ilúvatar.
> They were able to sing such beautiful music that the world was created out of it.

That is, the *Ainur* were the gods in Lord of the Rings who created and shaped the world.
Likewise, this software will create and shape the virtual world in which workloads on the ExPECA testbed will live.

## Setting up for development

1. Clone this repository.
   Note that we use submodules to link against related repositories on the ExPECA GitHub organization, and as such the cloning process is slightly different.
   The easiest way of doing it is by adding the `--recurse-submodules` flag when initially cloning: `git clone --recurse-submodules git@github.com:KTH-EXPECA/Ainur.git`.
   Alternatively, if by accident you cloned this repository as you normally would, you can initialize the submodules from inside the repo itself:

   ```bash
   # we clone the repository as we normally would
   $ git clone git@github.com:KTH-EXPECA/Ainur.git
   Cloning into 'Ainur'...
   ...

   # afterwards, move into the repository and initialize the submodules
   $ cd Ainur

   $ git submodule init

   $ git submodule update

   ```

2. Move into the repository, create a Python 3.9+ virtual environment (requires [virtualenv](https://pypi.org/project/virtualenv/)), and activate it:

    ``` bash
    $ cd Ainur

    $ python -m virtualenv --python=python3.9 ./venv
    created virtual environment CPython3.9.6.final.0-64 in 150ms
    creator CPython3Posix(dest=/test/venv, clear=False, no_vcs_ignore=False, global=False)
    seeder FromAppData(download=False, pip=bundle, setuptools=bundle, wheel=bundle, via=copy, app_data_dir=/home/test/.local/share/virtualenv)
    added seed packages: pip==21.1.3, setuptools==57.4.0, wheel==0.37.0
    activators BashActivator,CShellActivator,FishActivator,PowerShellActivator,PythonActivator

    $ source ./venv/bin/activate

    (venv) $ 
    ```

3. Install the required packages as specified by `requirements.txt`: `pip install -Ur requirements.txt`.


### Working with submodules

Linked submodules are "frozen" on a specific commit, not a branch as you might otherwise expect.
In case you wish to make changes to one and then link the new state to this repository, the procedure is the following:

1. Move into the submodule directory.
2. Checkout the desired branch: `git checkout <branch name>`
3. Make your changes.
4. Add, commit, and push your changes to upstream: `git add . && git commit -m <commit comment> && git push`.
5. Move back out into the main directory of this repository.
6. Add, commit, and push the modified submodule: `git add <submodule dir> && git commit -m <updated submodule X> && git push`.

In case the submodule was updated separately and you wish to add those changes to this project:

1. Move into the submodule directory.
2. Fetch all changes from the remote: `git fetch --all`.
3. Checkout the desired branch: `git checkout <branch name>`.
4. Pull the changes: `git pull`.
5. Move back out into the main directory of this repository.
6. Add, commit, and push the modified submodule: `git add <submodule dir> && git commit -m <updated submodule X> && git push`.

## Copyright & License

© Copyright 2021 -- ExPECA Project Members, KTH Royal Institute of Technology.

This code is licensed under an Apache License, version 2.0. See [LICENSE](LICENSE) for details.
