import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	authenticate,
	credentialToJSON,
	describeFailure,
	encode,
	fetchOptions,
	initPasskeyLogin,
	initPasskeyRegistration,
	nameFor,
	register,
	setStatus,
} from "../passkeys_admin/static/passkeys_admin/js/passkeys.js";

const LOGIN_DOM = `
	<form id="passkey-login-form"><input name="passkeys" value=""></form>
	<button id="passkey-verification-button"
		data-begin-url="/begin/"
		data-busy-label="Working"
		data-cancelled-label="Cancelled"
		data-error-label="Failed"></button>
	<p id="passkey-verification-status-message"></p>
`;

const REGISTER_DOM = `
	<button id="passkey-register-button"
		data-begin-url="/begin/"
		data-complete-url="/complete/"
		data-csrf-token="tok"
		data-busy-label="Working"
		data-cancelled-label="Cancelled"
		data-error-label="Failed"></button>
	<input id="passkey-name" value="">
	<p id="passkey-register-status-message"></p>
`;

const bytes = (...values) => new Uint8Array(values).buffer;

function fakeCredential(response) {
	return {
		id: "-_8",
		rawId: bytes(251, 255),
		type: "public-key",
		authenticatorAttachment: "platform",
		getClientExtensionResults: () => ({ credProps: { rk: true } }),
		response,
	};
}

const ASSERTION = fakeCredential({
	clientDataJSON: bytes(1),
	authenticatorData: bytes(2),
	signature: bytes(3),
	userHandle: null,
});

const ATTESTATION = fakeCredential({
	clientDataJSON: bytes(1),
	attestationObject: bytes(5),
});

function loginParts() {
	const form = document.getElementById("passkey-login-form");
	form.submit = vi.fn();
	return {
		button: document.getElementById("passkey-verification-button"),
		status: document.getElementById("passkey-verification-status-message"),
		form,
	};
}

function registerParts() {
	return {
		button: document.getElementById("passkey-register-button"),
		status: document.getElementById("passkey-register-status-message"),
	};
}

function optionsThen(second) {
	return vi
		.fn()
		.mockResolvedValueOnce({
			ok: true,
			json: async () => ({ publicKey: { challenge: "c" } }),
		})
		.mockResolvedValueOnce(second);
}

function stubCredentials(credentials) {
	vi.stubGlobal("navigator", { credentials });
}

beforeEach(() => {
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
	vi.stubGlobal("PublicKeyCredential", {
		parseRequestOptionsFromJSON: (options) => ({ parsed: "request", options }),
		parseCreationOptionsFromJSON: (options) => ({
			parsed: "creation",
			options,
		}),
	});
});

describe("setStatus", () => {
	it("does nothing without a node", () => {
		expect(() => setStatus(null, "x", "busy")).not.toThrow();
	});

	it("shows the message and the status", () => {
		document.body.innerHTML = REGISTER_DOM;
		const { status } = registerParts();
		setStatus(status, "Working", "busy");
		expect(status.textContent).toBe("Working");
		expect(status.classList.contains("visible")).toBe(true);
		expect(status.getAttribute("data-status-enum")).toBe("busy");
	});

	it("drops the status attribute when none is given", () => {
		document.body.innerHTML = REGISTER_DOM;
		const { status } = registerParts();
		setStatus(status, "Working", "busy");
		setStatus(status, "Done");
		expect(status.hasAttribute("data-status-enum")).toBe(false);
	});
});

describe("encode", () => {
	it("writes base64url without padding", () => {
		expect(encode(bytes(251, 255))).toBe("-_8");
		expect(encode(bytes(102, 111, 111, 98))).toBe("Zm9vYg");
	});

	it("encodes an empty buffer as an empty string", () => {
		expect(encode(bytes())).toBe("");
	});
});

describe("credentialToJSON", () => {
	it("serialises an assertion the way the server reads it", () => {
		expect(credentialToJSON(ASSERTION)).toEqual({
			id: "-_8",
			rawId: "-_8",
			type: "public-key",
			authenticatorAttachment: "platform",
			clientExtensionResults: { credProps: { rk: true } },
			response: {
				clientDataJSON: "AQ",
				authenticatorData: "Ag",
				signature: "Aw",
			},
		});
	});

	it("serialises an attestation the way the server reads it", () => {
		expect(credentialToJSON(ATTESTATION).response).toEqual({
			clientDataJSON: "AQ",
			attestationObject: "BQ",
		});
	});

	it("needs nothing but the credential's own fields", () => {
		const serialised = JSON.parse(JSON.stringify(credentialToJSON(ASSERTION)));
		expect(serialised.rawId).toBe("-_8");
		expect(serialised.response.signature).toBe("Aw");
	});
});

describe("fetchOptions", () => {
	it("returns the public key options the server issued", async () => {
		document.body.innerHTML = LOGIN_DOM;
		vi.stubGlobal("fetch", optionsThen({}));
		const { button } = loginParts();
		expect(await fetchOptions(button)).toEqual({ challenge: "c" });
		expect(fetch).toHaveBeenCalledWith("/begin/");
	});

	it("throws when the server refuses", async () => {
		document.body.innerHTML = LOGIN_DOM;
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
		const { button } = loginParts();
		await expect(fetchOptions(button)).rejects.toThrow("options");
	});
});

describe("describeFailure", () => {
	it("reports a cancelled ceremony distinctly", () => {
		document.body.innerHTML = LOGIN_DOM;
		const { button } = loginParts();
		const error = new Error("no");
		error.name = "NotAllowedError";
		expect(describeFailure(button, error)).toBe("Cancelled");
	});

	it("falls back to the generic message", () => {
		document.body.innerHTML = LOGIN_DOM;
		const { button } = loginParts();
		expect(describeFailure(button, new Error("boom"))).toBe("Failed");
		expect(describeFailure(button, undefined)).toBe("Failed");
	});
});

describe("authenticate", () => {
	it("asks the browser with the parsed options", async () => {
		document.body.innerHTML = LOGIN_DOM;
		vi.stubGlobal("fetch", optionsThen({}));
		const get = vi.fn(async () => ASSERTION);
		stubCredentials({ get });
		const { button, status, form } = loginParts();
		await authenticate(button, status, form);
		expect(get).toHaveBeenCalledWith({
			publicKey: { parsed: "request", options: { challenge: "c" } },
		});
	});

	it("fills the hidden field and submits the form", async () => {
		document.body.innerHTML = LOGIN_DOM;
		vi.stubGlobal("fetch", optionsThen({}));
		stubCredentials({ get: vi.fn(async () => ASSERTION) });
		const { button, status, form } = loginParts();
		await authenticate(button, status, form);
		expect(
			JSON.parse(form.querySelector('input[name="passkeys"]').value),
		).toEqual(credentialToJSON(ASSERTION));
		expect(form.submit).toHaveBeenCalledTimes(1);
	});

	it("reports a cancelled ceremony and re-enables the button", async () => {
		document.body.innerHTML = LOGIN_DOM;
		const cancelled = new Error("no");
		cancelled.name = "NotAllowedError";
		vi.stubGlobal("fetch", optionsThen({}));
		stubCredentials({
			get: vi.fn(async () => {
				throw cancelled;
			}),
		});
		const { button, status, form } = loginParts();
		await authenticate(button, status, form);
		expect(button.disabled).toBe(false);
		expect(status.textContent).toBe("Cancelled");
		expect(form.submit).not.toHaveBeenCalled();
	});

	it("reports a failure to fetch the options", async () => {
		document.body.innerHTML = LOGIN_DOM;
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
		const { button, status, form } = loginParts();
		await authenticate(button, status, form);
		expect(status.textContent).toBe("Failed");
	});
});

describe("register", () => {
	it("asks the browser with the parsed options", async () => {
		document.body.innerHTML = REGISTER_DOM;
		vi.stubGlobal("location", { reload: vi.fn() });
		const create = vi.fn(async () => ATTESTATION);
		stubCredentials({ create });
		vi.stubGlobal(
			"fetch",
			optionsThen({ json: async () => ({ status: "OK" }) }),
		);
		const { button, status } = registerParts();
		await register(button, status);
		expect(create).toHaveBeenCalledWith({
			publicKey: { parsed: "creation", options: { challenge: "c" } },
		});
	});

	it("reloads the page after a successful enrolment", async () => {
		document.body.innerHTML = REGISTER_DOM;
		const reload = vi.fn();
		vi.stubGlobal("location", { reload });
		stubCredentials({ create: vi.fn(async () => ATTESTATION) });
		vi.stubGlobal(
			"fetch",
			optionsThen({ json: async () => ({ status: "OK" }) }),
		);
		const { button, status } = registerParts();
		await register(button, status);
		expect(reload).toHaveBeenCalledTimes(1);
	});

	it("reports a rejected enrolment and re-enables the button", async () => {
		document.body.innerHTML = REGISTER_DOM;
		stubCredentials({ create: vi.fn(async () => ATTESTATION) });
		vi.stubGlobal(
			"fetch",
			optionsThen({ json: async () => ({ status: "ERR" }) }),
		);
		const { button, status } = registerParts();
		await register(button, status);
		expect(button.disabled).toBe(false);
		expect(status.textContent).toBe("Failed");
	});

	it("sends the credential, the csrf token and the chosen name", async () => {
		document.body.innerHTML = REGISTER_DOM;
		document.getElementById("passkey-name").value = "YubiKey";
		vi.stubGlobal("location", { reload: vi.fn() });
		stubCredentials({ create: vi.fn(async () => ATTESTATION) });
		const fetchMock = optionsThen({ json: async () => ({ status: "OK" }) });
		vi.stubGlobal("fetch", fetchMock);
		const { button, status } = registerParts();
		await register(button, status);
		const [url, options] = fetchMock.mock.calls[1];
		expect(url).toBe("/complete/");
		expect(options.headers["X-CSRFToken"]).toBe("tok");
		expect(JSON.parse(options.body)).toEqual({
			...credentialToJSON(ATTESTATION),
			key_name: "YubiKey",
		});
	});

	it("reports a failure to fetch the options", async () => {
		document.body.innerHTML = REGISTER_DOM;
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
		const { button, status } = registerParts();
		await register(button, status);
		expect(status.textContent).toBe("Failed");
	});
});

describe("nameFor", () => {
	it("returns an empty name when the field is absent", () => {
		expect(nameFor()).toBe("");
	});

	it("trims the name the operator typed", () => {
		document.body.innerHTML = REGISTER_DOM;
		document.getElementById("passkey-name").value = "  MacBook  ";
		expect(nameFor()).toBe("MacBook");
	});
});

describe("initialisation", () => {
	it("does nothing when neither button is present", () => {
		expect(() => initPasskeyLogin(document)).not.toThrow();
		expect(() => initPasskeyRegistration(document)).not.toThrow();
	});

	it("authenticates on click", async () => {
		document.body.innerHTML = LOGIN_DOM;
		vi.stubGlobal("fetch", optionsThen({}));
		stubCredentials({ get: vi.fn(async () => ASSERTION) });
		const { button, form } = loginParts();
		initPasskeyLogin(document);
		button.click();
		await vi.waitFor(() => expect(form.submit).toHaveBeenCalledTimes(1));
	});

	it("registers on click", async () => {
		document.body.innerHTML = REGISTER_DOM;
		vi.stubGlobal("location", { reload: vi.fn() });
		stubCredentials({ create: vi.fn(async () => ATTESTATION) });
		const fetchMock = optionsThen({ json: async () => ({ status: "OK" }) });
		vi.stubGlobal("fetch", fetchMock);
		initPasskeyRegistration(document);
		registerParts().button.click();
		await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
	});
});
