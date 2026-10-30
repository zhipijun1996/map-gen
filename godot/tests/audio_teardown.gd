extends RefCounted
## Actual test worlds only: stop owned service/fallback audio and observe release.
static func drain_world(world: Node, timeout_msec: int = 1000) -> bool:
	var started := Time.get_ticks_msec()
	var pending: Array[WeakRef] = []
	var owners: Array[Dictionary] = []
	for voice: AudioStreamPlayer2D in world.find_children("*", "AudioStreamPlayer2D", true, false):
		if voice.has_stream_playback():
			owners.append({"node":str(voice.get_path()),"stream":voice.stream.resource_path if voice.stream != null else "","playback_id":voice.get_stream_playback().get_instance_id()})
			pending.append(weakref(voice.get_stream_playback()))
		voice.stop()
		voice.stream = null
	for audio: GameAudio in world.get_tree().get_nodes_in_group(&"game_audio"):
		if not world.is_ancestor_of(audio): continue
		owners.append({"node":str(audio.get_path()),"service":"GameAudio","played":audio.played.duplicate()})
		if not await audio.shutdown(maxi(0,timeout_msec-(Time.get_ticks_msec()-started))):
			print("TEST AUDIO TEARDOWN: ",JSON.stringify({"released":false,"seconds":float(Time.get_ticks_msec()-started)/1000.0,"owners":owners}))
			return false
	# The formal App now owns music as well as SFX. Observe its actual backend
	# release within the same original total budget; fixed-frame tests may quit
	# before the audio server's real-time release otherwise completes.
	for music: GameMusic in world.get_tree().get_nodes_in_group(&"game_music"):
		if not world.is_ancestor_of(music): continue
		owners.append({"node":str(music.get_path()),"service":"GameMusic","track":str(music.requested_track),"starts":music.starts.duplicate()})
		if not await music.shutdown(maxi(0,timeout_msec-(Time.get_ticks_msec()-started))):
			print("TEST AUDIO TEARDOWN: ",JSON.stringify({"released":false,"seconds":float(Time.get_ticks_msec()-started)/1000.0,"owners":owners}))
			return false
	while pending.any(func(reference: WeakRef) -> bool: return reference.get_ref() != null):
		if Time.get_ticks_msec()-started >= timeout_msec:
			print("TEST AUDIO TEARDOWN: ",JSON.stringify({"released":false,"seconds":float(Time.get_ticks_msec()-started)/1000.0,"owners":owners}))
			return false
		await world.get_tree().process_frame
	print("TEST AUDIO TEARDOWN: ",JSON.stringify({"released":true,"seconds":float(Time.get_ticks_msec()-started)/1000.0,"owners":owners}))
	return true

## This consumer must observe queue_free before waiting for its audio backend.
static func stop_fallback_voices(world: Node) -> Dictionary:
	var started := Time.get_ticks_msec()
	var pending: Array[WeakRef] = []
	var owners: Array[Dictionary] = []
	for voice: AudioStreamPlayer2D in world.find_children("*", "AudioStreamPlayer2D", true, false):
		if voice.has_stream_playback():
			owners.append({"node":str(voice.get_path()),"stream":voice.stream.resource_path if voice.stream != null else "","playback_id":voice.get_stream_playback().get_instance_id()})
			pending.append(weakref(voice.get_stream_playback()))
		voice.stop()
		voice.stream = null
	return {"started_msec":started,"pending":pending,"owners":owners}

static func wait_fallback_release(receipt: Dictionary, timeout_msec: int = 1000) -> bool:
	var pending: Array[WeakRef] = receipt["pending"]
	while pending.any(func(reference: WeakRef) -> bool: return reference.get_ref() != null):
		if Time.get_ticks_msec()-int(receipt["started_msec"]) >= timeout_msec:
			print("TEST FALLBACK RELEASE: ",JSON.stringify({"released":false,"seconds":float(Time.get_ticks_msec()-int(receipt["started_msec"]))/1000.0,"owners":receipt["owners"]}))
			return false
		await (Engine.get_main_loop() as SceneTree).process_frame
	print("TEST FALLBACK RELEASE: ",JSON.stringify({"released":true,"seconds":float(Time.get_ticks_msec()-int(receipt["started_msec"]))/1000.0,"owners":receipt["owners"]}))
	return true
