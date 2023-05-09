import credentials from "./credentials.js";
import {
	prompt,
	fixWidth,
	printRoomList,
	printMessages,
	printMemberList,
	printRoomInfo,
	addCommand
} from "./io.js";
import { start, verifyRoom, getRoomList, clearDevices } from "./matrix.js";
import sdk from "./matrix-importer.js";
import type { Room, EventType } from "../../../lib/index.js";

let roomList: Room[] = [];
let viewingRoom: Room | null = null;

const client = await start(credentials);

client.on(sdk.ClientEvent.Room, () => {
	roomList = getRoomList(client);

	if (!viewingRoom) {
		printRoomList(roomList);
	}

	prompt();
});

client.on(sdk.RoomEvent.Timeline, async(event, room) => {
	const type = event.getType() as EventType;

	if (![sdk.EventType.RoomMessage, sdk.EventType.RoomMessageEncrypted].includes(type)) {
		return;
	}

	if (room != null && room.roomId !== viewingRoom?.roomId) {
		return;
	}

	await client.decryptEventIfNeeded(event);

	prompt(event.getContent().body);
});

addCommand("/help", () => {
	const displayCommand = (command: string, description: string) => {
		console.log(`  ${fixWidth(command, 20)} : ${description}`);
	};

	console.log("Global commands:");
	displayCommand("/help", "Show this help.");
	displayCommand("/quit", "Quit the program.");
	displayCommand("/cleardevices", "Clear all other devices from this account.");

	console.log("Room list index commands:");
	displayCommand("/join <index>", "Join a room, e.g. '/join 5'");

	console.log("Room commands:");
	displayCommand("/exit", "Return to the room list index.");
	displayCommand("/send <message>", "Send a message to the room, e.g. '/send Hello World.'");
	displayCommand("/members", "Show the room member list.");
	displayCommand("/invite @foo:bar", "Invite @foo:bar to the room.");
	displayCommand("/roominfo", "Display room info e.g. name, topic.");
});

addCommand("/quit", () => {
	process.exit();
});

addCommand("/cleardevices", async () => {
	await clearDevices(client);
});

addCommand("/join", async (index) => {
	if (viewingRoom != null) {
		return "You must first exit your current room.";
	}

	viewingRoom = roomList[index];

	if (viewingRoom == null) {
		return "Invalid Room.";
	}

	if (viewingRoom.getMember(client.getUserId() ?? "")?.membership === sdk.JoinRule.Invite) {
		await client.joinRoom(viewingRoom.roomId);
	}

	await verifyRoom(client, viewingRoom);
	await client.roomInitialSync(viewingRoom.roomId, 20);

	printMessages(viewingRoom);
});

addCommand("/exit", () => {
	viewingRoom = null;
	printRoomList(roomList);
});

addCommand("/invite", async (userId) => {
	if (viewingRoom == null) {
		return "You must first join a room.";
	}

	try {
		await client.invite(viewingRoom.roomId, userId);
	} catch (error) {
		return `/invite Error: ${error}`;
	}
});

addCommand("/members", async () => {
	if (viewingRoom == null) {
		return "You must first join a room.";
	}

	printMemberList(viewingRoom);
});

addCommand("/roominfo", async () => {
	if (viewingRoom == null) {
		return "You must first join a room.";
	}

	printMemberList(viewingRoom);
});

addCommand("/roominfo", async () => {
	if (viewingRoom == null) {
		return "You must first join a room.";
	}

	printRoomInfo(viewingRoom);
});

addCommand("/send", async (...tokens) => {
	if (viewingRoom == null) {
		return "You must first join a room.";
	}

	console.log(tokens);
	console.log(tokens.join(" "));

	const message = {
		msgtype: sdk.MsgType.Text,
		body: tokens.join(" ")
	};

	await client.sendMessage(viewingRoom.roomId, message);
});

roomList = getRoomList(client);
printRoomList(roomList);
prompt();
