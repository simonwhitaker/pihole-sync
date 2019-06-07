# Introduction

If you have multiple devices running [Pi-hole](https://pi-hole.net), keeping whitelists and blacklists in sync across devices can be a chore.

pihole-sync helps keep those lists in sync across your devices.

Note: pihole-sync syncs whitelists and blacklists: the ones you see in the Whitelist and Blacklist tabs in the Pi-hole admin page. **It doesn't sync blocklists** (the URLs of lists of domains configured in Settings > Blocklists).

# Setup

```
cp settings.py.example settings.py
```

Now edit settings.py and add details for each of the devices on your network
that are running Pi-hole.

# Usage

```sh
python3 sync.py
```
