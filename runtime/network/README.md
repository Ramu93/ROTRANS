# network

Implements the network layer.


## Changelog

### Version 2.7.1

- Fixed a major issue that prevented message from being received if a positive poll timeout was used.

### Version 2.7

- Messages now have a field that contains the `sender` and the flag `is_direct`.
- Receive and Publish socket fields in PeerContactInfo are now optional. 
- Messages are authenticated on the network level.
- Stale connections are detected and removed.
- Peer reintroduce themselves to silent peers.


### Version 2.6

- Added: Data-driven test annotation in `nettesthelpers.data_tester`
- Bug-fixes in nettesthelpers.MsgRecorder.
- Fix in BaseApp: if force_maintenance argument is not defined in the subclasses, it tries the old signature instead.

### Version 2.5

- New `structures.ItemType`: `UNSPENT_WALLET_COLLECTION`. 
  It can be used to denote that the collection of wallets are considered spent. 
  Other agents can reply with any confirmed transactions that are spending those presumably unspent wallets.

### Version 2.4

 - `MessageHandler.perform_maintenance` now offers the `force_maintenance` flag.
   It allows the caller to signal that all pending tasks are to be performed regardless of timers or other events. 
   Can be used in testing.
 - `settings.NetStatSettings` now configures the way messages and items are serialized.

