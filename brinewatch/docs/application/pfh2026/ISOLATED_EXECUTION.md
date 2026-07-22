# Isolated HoloOcean execution

BrineWatch custom-engine runs use a unique instance namespace and never attach
to, stop, or modify another HoloOcean process. The recommended entry point is:

```powershell
cd brinewatch
conda run -n ocean python scripts\run_isolated_custom_session.py
```

The launcher generates an ID such as `brinewatch-a1b2c3d4e5f6` and applies it
to the engine and client. HoloOcean appends that ID to all three Windows named
semaphores and to every shared-memory mapping. This removes the empty-suffix
collision that existed in the previous custom attach path.

Each run also receives a private directory under
`<repo>/.runtime/holoocean/<instance-id>/` containing:

- `work/` - process working directory;
- `outputs/` - isolated run outputs;
- `temp/` - `TEMP` and `TMP` for engine and client;
- `cache/local/` and `cache/shared/` - Unreal derived-data caches;
- `octrees/` - the acoustic octree cache selected by `-OctreeCacheRoot`;
- `logs/` - Unreal absolute log and captured standard output;
- `session_manifest.json` and `run_manifest.json` - IPC names, commands,
  owned PIDs, timestamps, and read-only before/after process inventories.

At shutdown the launcher terminates only the exact Unreal PID it created.
Existing HoloOcean or Unreal processes are recorded for audit purposes but are
never signalled. If another process causes GPU pressure or black frames, the
BrineWatch capture fails its image-quality gate and can be retried; it does not
attempt to recover by killing the competing process.

For a manual two-terminal run, choose one unique ID and export it in both
terminals:

```powershell
$env:BRINEWATCH_HOLOOCEAN_INSTANCE_ID = "brinewatch-$([guid]::NewGuid().ToString('N').Substring(0,12))"
python scripts\launch_custom_engine.py --clear-cache
```

Then use the same `BRINEWATCH_HOLOOCEAN_INSTANCE_ID` value in the client
terminal. The one-command launcher is preferred because it guarantees PID
ownership and directory consistency automatically.
