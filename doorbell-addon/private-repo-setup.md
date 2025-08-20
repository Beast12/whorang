# Setting Up Private Repository Access in Home Assistant

## Current Issue
The `pkg_resources` warning you're seeing is from HA's Cast component, not your addon. However, for private repositories, you need special setup.

## Option 1: Local Installation (Recommended)
```bash
# Use the install script we created
sudo ./install-local.sh
```

## Option 2: Private Repository Access via HACS

### Step 1: Add as Custom Repository
1. Go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add: `https://github.com/Beast12/whorang`
3. Category: **Add-on**
4. **Note**: This requires the repo to be public or you need a GitHub token

### Step 3: GitHub Token for Private Access
If keeping repo private, create a GitHub token:

1. **GitHub Settings → Developer settings → Personal access tokens**
2. Generate token with `repo` scope
3. **HACS Settings → Configure → GitHub Personal Access Token**
4. Enter your token

## Option 3: Manual Repository Addition

### Add to repositories.yaml
```yaml
# In your HA config directory
repositories:
  - url: https://github.com/Beast12/whorang
    type: addon
    token: your_github_token_here  # Optional for private repos
```

## Option 4: Make Repository Public (Simplest)

If you're comfortable making it public:
1. **GitHub → Settings → General → Danger Zone → Change visibility**
2. Make repository public
3. Add to HACS normally

## Recommended Approach for Testing

**Use local installation** since it's:
- ✅ Works immediately with private repos
- ✅ No GitHub token needed  
- ✅ Full control over updates
- ✅ Easy to modify and test

```bash
cd /home/koen/Github/whorang/doorbell-addon
sudo ./install-local.sh
sudo systemctl restart hassio-supervisor
```

Then install via **Settings → Add-ons → Local add-ons**
