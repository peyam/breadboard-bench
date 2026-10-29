# Re-render every PC-2 view with grey address/step wires (GPU). Run from C:\Users\peyam\pc2-render
$ErrorActionPreference = "Continue"
$env:PYTHONPATH = "C:\Users\peyam\pc2-render\pylib"
$env:BB_GPU = "1"
$B = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$R = "C:\Users\peyam\pc2-render\renders"
$O = "C:\Users\peyam\pc2-render\out"
New-Item -ItemType Directory -Force -Path $O | Out-Null
Set-Location $R
$jobs = @()
foreach ($s in "a-register","front-panel","clock","bus","b-register","alu","flags","program-counter","memory-address","ram","instruction-register","output","display-driver","display","input","control-sequencer","control-roms") {
  $jobs += ,@("board", $s, "$O\board-$s.png", "1950", "1100", "40")
}
$jobs += ,@("machine", "$O\machine.png", "1950", "1300", "40")
$jobs += ,@("machine", "$O\machine-top.png", "1950", "1300", "32", "top")
$jobs += ,@("closeup", "$O\chip-closeup.png", "1950", "1100", "40")
$jobs += ,@("display", "$O\display-lit.png", "1950", "1100", "40")
$jobs += ,@("programmer", "$O\programmer.png", "1950", "1100", "40")
$jobs += ,@("analyser", "$O\logic-analyser.png", "1950", "1100", "40")
$jobs += ,@("machine", "$O\machine-hires.png", "3600", "2400", "64")
foreach ($j in $jobs) {
  $t0 = Get-Date
  & $B -b --python-use-system-env --python build_scene.py -- @j *> "$O\last.log"
  $name = ($j | Where-Object { $_ -like "*.png" })
  if (Test-Path $name) { $ok = "done" } else { $ok = "FAILED" }
  "$ok $name $([int]((Get-Date) - $t0).TotalSeconds)s" | Tee-Object -Append -FilePath "$O\progress.txt"
}
"ALL DONE" | Tee-Object -Append -FilePath "$O\progress.txt"
