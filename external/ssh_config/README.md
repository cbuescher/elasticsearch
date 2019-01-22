## Configure ssh environment for access to benchmark machines

The following instructions allow you to easily ssh to our benchmarking environment using aliases like:

```
ssh night-rally-1
```

## Prerequisites

1. Vault configured according to [infra instructions](https://github.com/elastic/infra/blob/master/docs/vault.md#github-auth) and environment variable `VAULT_ADDR` set in your shell.
2. OpenSSH version >=7.3p1. Check this with `ssh -V`.
3. \[Optional, macOS\] If you want auto-completion with bash:
    1. `brew install bash-completion2`
    2. Add the following to your `~/.bashrc`:
        ```
        if [ -f $(brew --prefix)/share/bash-completion/bash_completion ]; then
        export BASH_COMPLETION_COMPAT_DIR="$(brew --prefix)/etc/bash_completion.d"
        source $(brew --prefix)/share/bash-completion/bash_completion
        fi
        ```

## Setup

1. Create a `config.d` directory under your `~/.ssh`:

    ```
    mkdir ~/.ssh/config.d
    chmod 0700 ~/.ssh/config.d
    ```

2. Copy the files in `config.d/` found under this README.md file to the new config.d directory you created in 1:

    ```
    cp -r config.d/. ~/.ssh/config.d
    ```

3. Edit `~/.ssh/config.d/common` and change `<yourlocalsshuser>` in line 5 with the unix account you used in the [infra repo](https://github.com/elastic/infra/blob/master/docs/accessing-instances.md#ssh-access) when you submitted your public key.

4. Add the following include **at the top** of your `~/.ssh/config` (if you don't have a config file, create a new one):

    ```
    Include ~/.ssh/config.d/*
    ```

5. Test your setup:

    ```
    ssh night-rally-1

    ssh lowmem-rally-1
    ```

## Troubleshooting

Most of the issues are either due to a non-working Vault configuration or due to a missing `.known_hosts` file.
For the latter, ensure that `.known_hosts` got copied correctly in step 2 and is present under `~/.ssh/config.d`.