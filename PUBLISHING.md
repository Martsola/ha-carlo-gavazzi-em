# Recreate and publish the GitHub repository

These commands assume the old GitHub repository has been deleted and this clean package has been extracted locally.

## Create the repository

Open Command Prompt in the extracted repository folder, then run:

```bat
git init
git add .
git commit -m "Initial clean release v1.0.0"
git branch -M main
gh repo create bfulham/ha-carlo-gavazzi-em --public --source=. --remote=origin --push --description "Home Assistant integration for Carlo Gavazzi EM270 and EM280 meters over Modbus TCP gateways"
```

Add the HACS topics:

```bat
gh repo edit bfulham/ha-carlo-gavazzi-em --add-topic home-assistant --add-topic hacs --add-topic integration --add-topic modbus --add-topic modbus-tcp --add-topic carlo-gavazzi --add-topic em270 --add-topic em280
```

Wait for **Lint** and **Validate** to pass.

## Create the first release

```bat
git tag -a v1.0.0 -m "Carlo Gavazzi EM v1.0.0"
git push origin v1.0.0
```

The tag-only Release workflow creates the GitHub release and attaches `carlo_gavazzi_em.zip` plus its SHA-256 checksum.

## Install cleanly in Home Assistant

Before installing the recreated repository:

1. Remove the old integration from HACS if present.
2. Delete `/config/custom_components/carlo_gavazzi_em` if it remains.
3. Restart Home Assistant.
4. Add the recreated repository to HACS as a custom Integration repository.
5. Install `v1.0.0` and restart Home Assistant again.
