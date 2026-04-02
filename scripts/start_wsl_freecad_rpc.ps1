$ErrorActionPreference = "Stop"

$scriptWslPath = "/mnt/d/workspace/skills_test/scripts/start_freecad_rpc_xvfb_wsl.sh"

wsl -d Ubuntu-24.04 -- bash -lc @"
cp '$scriptWslPath' /root/start_freecad_rpc_xvfb.sh
chmod +x /root/start_freecad_rpc_xvfb.sh
/root/start_freecad_rpc_xvfb.sh
"@
