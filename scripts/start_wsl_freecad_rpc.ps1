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

wsl -d Ubuntu-24.04 -- bash -lc @"
cp '$($selectedScript.Source)' '$($selectedScript.Target)'
chmod +x '$($selectedScript.Target)'
'$($selectedScript.Target)'
"@
