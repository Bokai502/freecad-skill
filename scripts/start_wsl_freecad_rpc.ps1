param(
    [ValidateSet("Headless", "Gui")]
    [string]$Mode = "Headless",
    [switch]$Gui
)

$ErrorActionPreference = "Stop"

if ($Gui) {
    $Mode = "Gui"
}

$scriptMap = @{
    Headless = @{
        Source = "/mnt/d/workspace/skills_test/scripts/start_freecad_rpc_xvfb_wsl.sh"
        Target = "/root/start_freecad_rpc_xvfb.sh"
    }
    Gui = @{
        Source = "/mnt/d/workspace/skills_test/scripts/start_freecad_gui_wsl.sh"
        Target = "/root/start_freecad_gui.sh"
    }
}

$selectedScript = $scriptMap[$Mode]

$src = $selectedScript.Source
$tgt = $selectedScript.Target

wsl -d Ubuntu-24.04 -u root -- bash -c "tr -d '\r' < '$src' > '$tgt'"
wsl -d Ubuntu-24.04 -u root -- bash -c "chmod +x '$tgt'"
wsl -d Ubuntu-24.04 -u root -- bash -l "$tgt"
