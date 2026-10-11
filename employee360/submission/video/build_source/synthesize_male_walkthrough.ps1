Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.SelectVoice('Microsoft George')
$speaker.Rate = 0
$segments = Get-Content walkthrough_male\narration.json -Raw | ConvertFrom-Json
foreach ($segment in $segments) {
    $audioPath = Join-Path (Get-Location) ('walkthrough_male\' + $segment.key + '.wav')
    $speaker.SetOutputToWaveFile($audioPath)
    $speaker.Speak($segment.text)
    $speaker.SetOutputToNull()
}
$speaker.Dispose()
Write-Output 'Male narration generated using Microsoft George.'
