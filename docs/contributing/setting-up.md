# Setting up for development

1. Clone the [repository](https://github.com/KTH-EXPECA/Ainur).
   Note that we use submodules to link against related repositories on the ExPECA GitHub organization, and as such the cloning process is slightly different.
   The easiest way of doing it is by adding the `--recurse-submodules` flag when initially cloning: `git clone --recurse-submodules git@github.com:KTH-EXPECA/Ainur.git`
   
   Alternatively, if by accident you cloned this repository without the `--recurse-submodules` flag, you can initialize the submodules from inside the repo itself:

   ```bash
   # we clone the repository as we normally would
   $ git clone git@github.com:KTH-EXPECA/Ainur.git
   Cloning into 'Ainur'...
   ...

   # afterwards, move into the repository and initialize the submodules
   $ cd Ainur

   $ git submodule init

   $ git submodule update
    ...
   ```

2. Move into the repository, create a Python 3.9+ [virtual environment](https://docs.python.org/3/library/venv.html).

3. Install the required Python packages as specified by `requirements.txt`: `pip install -Ur requirements.txt`.

4. Install the required Ansible packages as specified by `requirements.yml`: `ansible-galaxy install -r requirements.yml`

!!! note "A note on working with Git submodules"

    Linked submodules are "frozen" on a specific commit, not a branch as you might otherwise expect.
    In case you wish to make changes to one and then link the new state to this repository, the procedure is the following:

    1. Move into the submodule directory.
    2. Checkout the desired branch: `git checkout <branch name>`
    3. Make your changes.
    4. Add, commit, and push your changes to upstream: `git add . && git commit -m <commit comment> && git push`.
    5. Move back out into the main repository.
    6. Add, commit, and push the modified submodule: `git add <submodule dir> && git commit -m <updated submodule X> && git push`.

    In case the submodule was updated separately and you wish to add those changes to this project:

    1. Move into the submodule directory.
    2. Fetch all changes from the remote: `git fetch --all`.
    3. Checkout the desired branch: `git checkout <branch name>`.
    4. Pull the changes: `git pull`.
    5. Move back out into the main repository.
    6. Add, commit, and push the modified submodule: `git add <submodule dir> && git commit -m <updated submodule X> && git push`.

## Prerequisites

Below is an incomplete list of prerequisites/assumptions Ainur makes with respect to the execution environment:

- Ansible is set up to be able to access the hosts.
- The Docker daemon on all hosts is configured to listen both locally (on a Unix socket), and remotely on a socket bound to port `2375/tcp`.
- TODO
