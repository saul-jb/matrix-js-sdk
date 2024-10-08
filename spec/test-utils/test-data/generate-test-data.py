#!/bin/env python
#
# Copyright 2023 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This file is a Python script to generate test data for crypto tests.

To run it:

python -m venv env
./env/bin/pip install cryptography canonicaljson
./env/bin/python generate-test-data.py > index.ts
"""

import base64
import json
import base58

from canonicaljson import encode_canonical_json
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives import hashes, padding, hmac
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from random import randbytes, seed

ALICE_DATA = {
    "TEST_USER_ID": "@alice:localhost",
    "TEST_DEVICE_ID": "test_device",
    "TEST_ROOM_ID": "!room:id",
    # any 32-byte string can be an ed25519 private key.
    "TEST_DEVICE_PRIVATE_KEY_BYTES": b"deadbeefdeadbeefdeadbeefdeadbeef",
    # any 32-byte string can be an curve25519 private key.
    "TEST_DEVICE_CURVE_PRIVATE_KEY_BYTES": b"deadmuledeadmuledeadmuledeadmule",

    "MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"doyouspeakwhaaaaaaaaaaaaaaaaaale",
    "USER_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"useruseruseruseruseruseruseruser",
    "SELF_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"selfselfselfselfselfselfselfself",

    # Private key for secure key backup. There are some sessions encrypted with this key in megolm-backup.spec.ts
    "B64_BACKUP_DECRYPTION_KEY": "dwdtCnMYpX08FsFyUbJmRd9ML4frwJkqsXf7pR25LCo=",

    "OTK": "j3fR3HemM16M7CWhoI4Sk5ZsdmdfQHsKL1xuSft6MSw"
}

BOB_DATA = {
    "TEST_USER_ID": "@bob:xyz",
    "TEST_DEVICE_ID": "bob_device",
    "TEST_ROOM_ID": "!room:id",
    # any 32-byte string can be an ed25519 private key.
    "TEST_DEVICE_PRIVATE_KEY_BYTES": b"Deadbeefdeadbeefdeadbeefdeadbeef",
    # any 32-byte string can be an curve25519 private key.
    "TEST_DEVICE_CURVE_PRIVATE_KEY_BYTES": b"Deadmuledeadmuledeadmuledeadmule",

    "MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"Doyouspeakwhaaaaaaaaaaaaaaaaaale",
    "ALT_MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"DoYouSpeakWhaaaaaaaaaaaaaaaaaale",
    "USER_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"Useruseruseruseruseruseruseruser",
    "SELF_CROSS_SIGNING_PRIVATE_KEY_BYTES": b"Selfselfselfselfselfselfselfself",

    # Private key for secure key backup. There are some sessions encrypted with this key in megolm-backup.spec.ts
    "B64_BACKUP_DECRYPTION_KEY": "DwdtCnMYpX08FsFyUbJmRd9ML4frwJkqsXf7pR25LCo=",

    "OTK": "j3fR3HemM16M7CWhoI4Sk5ZsdmdfQHsKL1xuSft6MSw"
}

def main() -> None:
    print(
        f"""\
/* Test data for cryptography tests
 *
 * Do not edit by hand! This file is generated by `./generate-test-data.py`
 */

import {{ IDeviceKeys, IMegolmSessionData }} from "../../../src/@types/crypto";
import {{ IDownloadKeyResult, IEvent }} from "../../../src";
import {{ KeyBackupSession, KeyBackupInfo }} from "../../../src/crypto-api/keybackup";

/* eslint-disable comma-dangle */

// Alice data

{build_test_data(ALICE_DATA)}
// Bob data

{build_test_data(BOB_DATA, "BOB_")}
""",
        end="",
    )

# Use static seed to have stable random test data upon new generation
seed(10)

def build_test_data(user_data, prefix = "") -> str:
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
             user_data["TEST_DEVICE_PRIVATE_KEY_BYTES"]
        )

    device_curve_key = x25519.X25519PrivateKey.from_private_bytes(
             user_data["TEST_DEVICE_CURVE_PRIVATE_KEY_BYTES"]
        )

    b64_public_key = encode_base64(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )

    device_data = {
        "algorithms": ["m.olm.v1.curve25519-aes-sha2", "m.megolm.v1.aes-sha2"],
        "device_id":  user_data["TEST_DEVICE_ID"],
        "keys": {
            f"curve25519:{user_data['TEST_DEVICE_ID']}": "F4uCNNlcbRvc7CfBz95ZGWBvY1ALniG1J8+6rhVoKS0",
            f"ed25519:{user_data['TEST_DEVICE_ID']}": b64_public_key,
        },
        "signatures": {user_data['TEST_USER_ID']: {}},
        "user_id": user_data["TEST_USER_ID"],
    }

    device_data["signatures"][user_data["TEST_USER_ID"]][f"ed25519:{user_data['TEST_DEVICE_ID']}"] = sign_json(
        device_data, private_key
    )

    master_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
        user_data["MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES"]
    )
    b64_master_public_key = encode_base64(
        master_private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    b64_master_private_key = encode_base64(user_data["MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES"])

    self_signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
        user_data["SELF_CROSS_SIGNING_PRIVATE_KEY_BYTES"]
    )
    b64_self_signing_public_key = encode_base64(
        self_signing_private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
    )
    b64_self_signing_private_key = encode_base64( user_data["SELF_CROSS_SIGNING_PRIVATE_KEY_BYTES"])

    user_signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
         user_data["USER_CROSS_SIGNING_PRIVATE_KEY_BYTES"]
    )
    b64_user_signing_public_key = encode_base64(
        user_signing_private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
    )
    b64_user_signing_private_key = encode_base64(user_data["USER_CROSS_SIGNING_PRIVATE_KEY_BYTES"])

    backup_decryption_key = x25519.X25519PrivateKey.from_private_bytes(
        base64.b64decode(user_data["B64_BACKUP_DECRYPTION_KEY"])
    )
    b64_backup_public_key = encode_base64(
        backup_decryption_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )

    backup_data = {
        "algorithm": "m.megolm_backup.v1.curve25519-aes-sha2",
        "version": "1",
        "auth_data": {
            "public_key": b64_backup_public_key,
        },
    }
    # sign with our device key
    sig = sign_json(backup_data["auth_data"], private_key)
    backup_data["auth_data"]["signatures"] = {
        user_data["TEST_USER_ID"]: {f"ed25519:{user_data['TEST_DEVICE_ID']}": sig}
    }

    set_of_exported_room_keys = [build_exported_megolm_key(device_curve_key)[0], build_exported_megolm_key(device_curve_key)[0]]

    additional_exported_room_key, additional_exported_ed_key = build_exported_megolm_key(device_curve_key)
    ratcheted_exported_room_key = symetric_ratchet_step_of_megolm_key(additional_exported_room_key, additional_exported_ed_key)

    otk_to_sign = {
        "key": user_data['OTK']
    }
    # sign our public otk key with our device key
    otk = sign_json(otk_to_sign, private_key)
    otks = {
        user_data["TEST_USER_ID"]: {
            user_data['TEST_DEVICE_ID']: {
                 "signed_curve25519:AAAAHQ": {
                    "key": user_data["OTK"],
                    "signatures": {
                        user_data["TEST_USER_ID"]: {f"ed25519:{user_data['TEST_DEVICE_ID']}": otk}
                    }
                 }
            }
        }
    }


    backed_up_room_key = encrypt_megolm_key_for_backup(additional_exported_room_key, backup_decryption_key.public_key())

    clear_event, encrypted_event = generate_encrypted_event_content(additional_exported_room_key, additional_exported_ed_key, device_curve_key)

    backup_recovery_key = export_recovery_key(user_data["B64_BACKUP_DECRYPTION_KEY"])

    result = f"""\
export const {prefix}TEST_USER_ID = "{user_data['TEST_USER_ID']}";
export const {prefix}TEST_DEVICE_ID = "{user_data['TEST_DEVICE_ID']}";
export const {prefix}TEST_ROOM_ID = "{user_data['TEST_ROOM_ID']}";

/** The base64-encoded public ed25519 key for this device */
export const {prefix}TEST_DEVICE_PUBLIC_ED25519_KEY_BASE64 = "{b64_public_key}";

/** Signed device data, suitable for returning from a `/keys/query` call */
export const {prefix}SIGNED_TEST_DEVICE_DATA: IDeviceKeys = {json.dumps(device_data, indent=4)};

/** base64-encoded public master cross-signing key */
export const {prefix}MASTER_CROSS_SIGNING_PUBLIC_KEY_BASE64 = "{b64_master_public_key}";

/** base64-encoded private master cross-signing key */
export const {prefix}MASTER_CROSS_SIGNING_PRIVATE_KEY_BASE64 = "{b64_master_private_key}";

/** base64-encoded public self cross-signing key */
export const {prefix}SELF_CROSS_SIGNING_PUBLIC_KEY_BASE64 = "{b64_self_signing_public_key}";

/** base64-encoded private self signing cross-signing key */
export const {prefix}SELF_CROSS_SIGNING_PRIVATE_KEY_BASE64 = "{b64_self_signing_private_key}";

/** base64-encoded public user cross-signing key */
export const {prefix}USER_CROSS_SIGNING_PUBLIC_KEY_BASE64 = "{b64_user_signing_public_key}";

/** base64-encoded private user signing cross-signing key */
export const {prefix}USER_CROSS_SIGNING_PRIVATE_KEY_BASE64 = "{b64_user_signing_private_key}";

/** Signed cross-signing keys data, also suitable for returning from a `/keys/query` call */
export const {prefix}SIGNED_CROSS_SIGNING_KEYS_DATA: Partial<IDownloadKeyResult> = {
        json.dumps(build_cross_signing_keys_data(user_data, user_data["MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES"]), indent=4)
};

/** Signed OTKs, returned by `POST /keys/claim` */
export const {prefix}ONE_TIME_KEYS = { json.dumps(otks, indent=4) };

/** base64-encoded backup decryption (private) key */
export const {prefix}BACKUP_DECRYPTION_KEY_BASE64 = "{ user_data['B64_BACKUP_DECRYPTION_KEY'] }";

/** Backup decryption key in export format */
export const {prefix}BACKUP_DECRYPTION_KEY_BASE58 = "{ backup_recovery_key }";

/** Signed backup data, suitable for return from `GET /_matrix/client/v3/room_keys/keys/{{roomId}}/{{sessionId}}` */
export const {prefix}SIGNED_BACKUP_DATA: KeyBackupInfo = { json.dumps(backup_data, indent=4) };

/** A set of megolm keys that can be imported via CryptoAPI#importRoomKeys */
export const {prefix}MEGOLM_SESSION_DATA_ARRAY: IMegolmSessionData[] = {
    json.dumps(set_of_exported_room_keys, indent=4)
};

/** An exported megolm session */
export const {prefix}MEGOLM_SESSION_DATA: IMegolmSessionData = {
        json.dumps(additional_exported_room_key, indent=4)
};

/** A ratcheted version of {prefix}MEGOLM_SESSION_DATA */
export const {prefix}RATCHTED_MEGOLM_SESSION_DATA: IMegolmSessionData = {
        json.dumps(ratcheted_exported_room_key, indent=4)
};

/** The key from {prefix}MEGOLM_SESSION_DATA, encrypted for backup using `m.megolm_backup.v1.curve25519-aes-sha2` algorithm*/
export const {prefix}CURVE25519_KEY_BACKUP_DATA: KeyBackupSession = {json.dumps(backed_up_room_key, indent=4)};

/** A test clear event */
export const {prefix}CLEAR_EVENT: Partial<IEvent> = {json.dumps(clear_event, indent=4)};

/** The encrypted CLEAR_EVENT by MEGOLM_SESSION_DATA */
export const {prefix}ENCRYPTED_EVENT: Partial<IEvent> = {json.dumps(encrypted_event, indent=4)};
"""

    alt_master_key = user_data.get("ALT_MASTER_CROSS_SIGNING_PRIVATE_KEY_BYTES")
    if alt_master_key is not None:
        result += f"""
/** A second set of signed cross-signing keys data, also suitable for returning from a `/keys/query` call */
export const {prefix}ALT_SIGNED_CROSS_SIGNING_KEYS_DATA: Partial<IDownloadKeyResult> = {
        json.dumps(build_cross_signing_keys_data(user_data, alt_master_key), indent=4)
};
"""

    return result

def build_cross_signing_keys_data(user_data, master_key_bytes) -> dict:
    """Build the signed cross-signing-keys data for return from /keys/query"""
    master_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(master_key_bytes)
    b64_master_public_key = encode_base64(
        master_private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )
    self_signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
         user_data["SELF_CROSS_SIGNING_PRIVATE_KEY_BYTES"]
    )
    b64_self_signing_public_key = encode_base64(
        self_signing_private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
    )
    user_signing_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
         user_data["USER_CROSS_SIGNING_PRIVATE_KEY_BYTES"]
    )
    b64_user_signing_public_key = encode_base64(
        user_signing_private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
    )
    # create without signatures initially
    cross_signing_keys_data = {
        "master_keys": {
             user_data["TEST_USER_ID"]: {
                "keys": {
                    f"ed25519:{b64_master_public_key}": b64_master_public_key,
                },
                "user_id": user_data["TEST_USER_ID"],
                "usage": ["master"],
            }
        },
        "self_signing_keys": {
            user_data["TEST_USER_ID"]: {
                "keys": {
                    f"ed25519:{b64_self_signing_public_key}": b64_self_signing_public_key,
                },
                "user_id": user_data["TEST_USER_ID"],
                "usage": ["self_signing"],
            },
        },
        "user_signing_keys": {
            user_data["TEST_USER_ID"]: {
                "keys": {
                    f"ed25519:{b64_user_signing_public_key}": b64_user_signing_public_key,
                },
                "user_id": user_data["TEST_USER_ID"],
                "usage": ["user_signing"],
            },
        },
    }
    # sign the sub-keys with the master
    for k in ["self_signing_keys", "user_signing_keys"]:
        to_sign = cross_signing_keys_data[k][user_data["TEST_USER_ID"]]
        sig = sign_json(to_sign, master_private_key)
        to_sign["signatures"] = {
            user_data["TEST_USER_ID"]: {f"ed25519:{b64_master_public_key}": sig}
        }

    return cross_signing_keys_data


def encode_base64(input_bytes: bytes) -> str:
    """Encode with unpadded base64"""
    output_bytes = base64.b64encode(input_bytes)
    output_string = output_bytes.decode("ascii")
    return output_string.rstrip("=")


def sign_json(json_object: dict, private_key: ed25519.Ed25519PrivateKey) -> str:
    """
    Sign the given json object

    Returns the base64-encoded signature of signing `input` following the Matrix
    JSON signature algorithm [1]

    [1]: https://spec.matrix.org/v1.7/appendices/#signing-details
    """
    signatures = json_object.pop("signatures", {})
    unsigned = json_object.pop("unsigned", None)

    signature = private_key.sign(encode_canonical_json(json_object))
    signature_base64 = encode_base64(signature)

    json_object["signatures"] = signatures
    if unsigned is not None:
        json_object["unsigned"] = unsigned

    return signature_base64

def build_exported_megolm_key(device_curve_key: x25519.X25519PrivateKey) -> tuple[dict, ed25519.Ed25519PrivateKey]:
    """
    Creates an exported megolm room key, as per https://gitlab.matrix.org/matrix-org/olm/blob/master/docs/megolm.md#session-export-format
    that can be imported via importRoomKeys API.
    Returns the exported key, the matching privat edKey (needed to encrypt)
    """
    index = 0
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(randbytes(32))
    # Just use radom bytes for the ratchet parts
    ratchet = randbytes(32 * 4)
    # exported key, start with version byte
    exported_key = bytearray(b'\x01')
    exported_key += index.to_bytes(4, 'big')
    exported_key += ratchet
    # KPub
    exported_key += private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


    megolm_export = {
        "algorithm": "m.megolm.v1.aes-sha2",
        "room_id": "!room:id",
        "sender_key": encode_base64(
            device_curve_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ),
        "session_id": encode_base64(
            private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ),
        "session_key": encode_base64(exported_key),
        "sender_claimed_keys": {
            "ed25519": encode_base64(ed25519.Ed25519PrivateKey.from_private_bytes(randbytes(32)).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        },
        "forwarding_curve25519_key_chain": [],
    }

    return megolm_export, private_key

def symetric_ratchet_step_of_megolm_key(previous: dict , megolm_private_key: ed25519.Ed25519PrivateKey) -> dict:

    """
    Very simple ratchet step from 0 to 1
    Used to generate a ratcheted key to test unknown message index.
    """
    session_key: str = previous["session_key"]

    # Get the megolm R0 from the export format
    decoded = base64.b64decode(session_key.encode("ascii"))
    ri = decoded[5:133]

    ri0 = ri[0:32]
    ri1 = ri[32:64]
    ri2 = ri[64:96]
    ri3 = ri[96:128]

    h = hmac.HMAC(ri3, hashes.SHA256())
    h.update(b'x\03')
    ri1_3 = h.finalize()

    index = 1
    private_key = megolm_private_key

    # exported key, start with version byte
    exported_key = bytearray(b'\x01')
    exported_key += index.to_bytes(4, 'big')
    exported_key += ri0
    exported_key += ri1
    exported_key += ri2
    exported_key += ri1_3
    # KPub
    exported_key += private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


    megolm_export = {
        "algorithm": "m.megolm.v1.aes-sha2",
        "room_id": "!room:id",
        "sender_key": previous["sender_key"],
        "session_id": previous["session_id"],
        "session_key": encode_base64(exported_key),
        "sender_claimed_keys": previous["sender_claimed_keys"],
        "forwarding_curve25519_key_chain": [],
    }

    return megolm_export

def encrypt_megolm_key_for_backup(session_data: dict, backup_public_key: x25519.X25519PublicKey) -> dict:

    """
    Encrypts an exported megolm key for key backup, using the m.megolm_backup.v1.curve25519-aes-sha2 algorithm.
    """
    data = encode_canonical_json(session_data)

    # Generate an ephemeral curve25519 key, and perform an ECDH with the ephemeral key
    # and the backup’s public key to generate a shared secret.
    # The public half of the ephemeral key, encoded using unpadded base64,
    # becomes the ephemeral property of the session_data.
    ephemeral_keypair = x25519.X25519PrivateKey.from_private_bytes(randbytes(32))
    shared_secret = ephemeral_keypair.exchange(backup_public_key)
    ephemeral = encode_base64(ephemeral_keypair.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

    # Using the shared secret, generate 80 bytes by performing an HKDF using SHA-256 as the hash,
    # with a salt of 32 bytes of 0, and with the empty string as the info.
    # The first 32 bytes are used as the AES key, the next 32 bytes are used as the MAC key,
    #  and the last 16 bytes are used as the AES initialization vector.
    salt = bytes(32)
    info = b""

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=80,
        salt=salt,
        info=info,
    )

    raw_key = hkdf.derive(shared_secret)
    aes_key = raw_key[:32]
    mac = raw_key[32:64]
    iv = raw_key[64:80]

    # Stringify the JSON object, and encrypt it using AES-CBC-256 with PKCS#7 padding.
    # This encrypted data, encoded using unpadded base64, becomes the ciphertext property of the session_data.
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    cipher_text = encode_base64(ct)

    # Pass the raw encrypted data (prior to base64 encoding) through HMAC-SHA-256 using the MAC key generated above.
    # The first 8 bytes of the resulting MAC are base64-encoded, and become the mac property of the session_data.
    h = hmac.HMAC(mac, hashes.SHA256())
    # h.update(ct)
    signature = h.finalize()
    mac = encode_base64(signature[:8])

    encrypted_key = {
        "first_message_index": 1,
        "forwarded_count": 0,
        "is_verified": False,
        "session_data": {
            "ciphertext": cipher_text,
            "ephemeral": ephemeral,
            "mac": mac
        }

    }

    return encrypted_key

def generate_encrypted_event_content(exported_key: dict, ed_key: ed25519.Ed25519PrivateKey, curve_key: x25519.X25519PrivateKey) -> tuple[dict, dict]:
    """
        Encrypts an event using the given key in session export format.
        Will not do any ratcheting, just encrypt at index 0.
    """

    clear_event = {
        "type": "m.room.message",
        "room_id": "!room:id",
        "sender": "@alice:localhost",
        "content": {
            "msgtype": "m.text",
            "body": "Hello world"
        }
    }

    session_key: str = exported_key["session_key"]

    # Get the megolm R0 from the export format
    decoded = base64.b64decode(session_key.encode("ascii"))
    r0 = decoded[5:133]

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=80,
        salt=bytes(32),
        info=b"MEGOLM_KEYS",
    )

    raw_key = hkdf.derive(r0)
    aes_key = raw_key[:32]
    mac = raw_key[32:64]
    aes_iv = raw_key[64:80]

    payload_json = {
        "room_id": clear_event["room_id"],
        "type": clear_event["type"],
        "content": clear_event["content"]
    }

    payload_string = encode_canonical_json(payload_json)

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv))
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()

    padded_data = padder.update(payload_string)
    padded_data += padder.finalize()

    ct = encryptor.update(padded_data) + encryptor.finalize()

    # The ratchet index i, and the cipher-text, are then packed
    # into a message as described in Message format. Then the entire message
    # (including the version bytes and all payload bytes) are passed through
    # HMAC-SHA-256. The first 8 bytes of the MAC are appended to the message.
    message = bytearray()
    message += b'\x03'
    # int tag for index
    message += b'\x08'
    # index is 0
    message += b'\x00'
    message += b'\x12'
    # probably works only for short messages
    message += len(ct).to_bytes(1, 'big')
    # encrypted data
    message += ct

    h = hmac.HMAC(mac, hashes.SHA256())
    h.update(message)
    signature = h.finalize()
    mac = signature[:8]

    message += mac

    # Finally, the authenticated message is signed using the Ed25519 keypair;
    # the 64 byte signature is appended to the message
    signature = ed_key.sign(bytes(message))

    message += signature

    cipher_text = encode_base64(message)

    encrypted_payload = {
        "algorithm" : "m.megolm.v1.aes-sha2",
        "sender_key" : encode_base64(curve_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "ciphertext" : cipher_text,
        "session_id" : exported_key["session_id"],
        "device_id" : "TEST_DEVICE"
    }

    encrypted_event = {
        "type": "m.room.encrypted",
        "room_id": "!room:id",
        "sender": "@alice:localhost",
        "content": encrypted_payload,
        "event_id": "$event1",
        "origin_server_ts": 1507753886000,
    }

    return clear_event, encrypted_event


def export_recovery_key(key_b64: str) -> str:
    """
        Export a private recovery key as a recovery key that can be presented to users.
        As per spec https://spec.matrix.org/v1.8/client-server-api/#recovery-key
    """
    private_key_bytes = base64.b64decode(key_b64)

    # The 256-bit curve25519 private key is prepended by the bytes 0x8B and 0x01
    export_bytes = bytearray()
    export_bytes += b'\x8b'
    export_bytes += b'\x01'

    export_bytes += private_key_bytes

    # All the bytes in the string above, including the two header bytes,
    # are XORed together to form a parity byte. This parity byte is appended to the byte string.
    parity_byte = 0 #b'\x8b' ^ b'\x01'
    [parity_byte := parity_byte ^ x for x in export_bytes]

    export_bytes += parity_byte.to_bytes(1, 'big')

    # The byte string is encoded using base58
    recovery_key = base58.b58encode(export_bytes).decode('utf-8')

    split = [recovery_key[i:i + 4] for i in range(0, len(recovery_key), 4)]
    return ' '.join(split)


if __name__ == "__main__":
    main()
