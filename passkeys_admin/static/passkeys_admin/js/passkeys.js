const RESPONSE_FIELDS = [
	"clientDataJSON",
	"attestationObject",
	"authenticatorData",
	"signature",
	"userHandle",
];

function setStatus(node, message, status) {
	if (!node) return;
	node.textContent = message;
	node.classList.add("visible");
	if (status) node.setAttribute("data-status-enum", status);
	else node.removeAttribute("data-status-enum");
}

function encode(buffer) {
	return btoa(String.fromCharCode(...new Uint8Array(buffer)))
		.replaceAll("+", "-")
		.replaceAll("/", "_")
		.replaceAll("=", "");
}

function credentialToJSON(credential) {
	const { response } = credential;
	return {
		id: credential.id,
		rawId: encode(credential.rawId),
		type: credential.type,
		authenticatorAttachment: credential.authenticatorAttachment,
		clientExtensionResults: credential.getClientExtensionResults(),
		response: Object.fromEntries(
			RESPONSE_FIELDS.filter((field) => response[field]).map((field) => [
				field,
				encode(response[field]),
			]),
		),
	};
}

async function fetchOptions(button) {
	const response = await fetch(button.dataset.beginUrl);
	if (!response.ok) throw new Error("options");
	return (await response.json()).publicKey;
}

function describeFailure(button, error) {
	if (error && error.name === "NotAllowedError")
		return button.dataset.cancelledLabel;
	return button.dataset.errorLabel;
}

function nameFor() {
	const field = document.getElementById("passkey-name");
	return field ? field.value.trim() : "";
}

async function authenticate(button, status, form) {
	button.disabled = true;
	setStatus(status, button.dataset.busyLabel, "busy");
	try {
		const publicKey = PublicKeyCredential.parseRequestOptionsFromJSON(
			await fetchOptions(button),
		);
		const assertion = await navigator.credentials.get({ publicKey });
		form.querySelector('input[name="passkeys"]').value = JSON.stringify(
			credentialToJSON(assertion),
		);
		form.submit();
	} catch (error) {
		button.disabled = false;
		setStatus(status, describeFailure(button, error), "error");
	}
}

async function register(button, status) {
	button.disabled = true;
	setStatus(status, button.dataset.busyLabel, "busy");
	try {
		const publicKey = PublicKeyCredential.parseCreationOptionsFromJSON(
			await fetchOptions(button),
		);
		const credential = await navigator.credentials.create({ publicKey });
		const completed = await fetch(button.dataset.completeUrl, {
			method: "POST",
			headers: { "X-CSRFToken": button.dataset.csrfToken },
			body: JSON.stringify({
				...credentialToJSON(credential),
				key_name: nameFor(),
			}),
		});
		const result = await completed.json();
		if (result.status !== "OK") throw new Error("rejected");
		globalThis.location.reload();
	} catch (error) {
		button.disabled = false;
		setStatus(status, describeFailure(button, error), "error");
	}
}

function initPasskeyLogin(root) {
	const button = root.querySelector("#passkey-verification-button");
	if (!button) return;
	const status = root.querySelector("#passkey-verification-status-message");
	const form = root.querySelector("#passkey-login-form");
	button.addEventListener("click", () => authenticate(button, status, form));
}

function initPasskeyRegistration(root) {
	const button = root.querySelector("#passkey-register-button");
	if (!button) return;
	const status = root.querySelector("#passkey-register-status-message");
	button.addEventListener("click", () => register(button, status));
}

initPasskeyLogin(document);
initPasskeyRegistration(document);

export {
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
};
