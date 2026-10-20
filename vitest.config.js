import { defineConfig } from "vitest/config";

export default defineConfig({
	test: {
		environment: "jsdom",
		coverage: {
			provider: "v8",
			include: ["passkeys_admin/static/passkeys_admin/js/passkeys.js"],
			reporter: ["text", "html"],
			thresholds: {
				branches: 100,
				functions: 100,
				lines: 100,
				statements: 100,
			},
		},
	},
});
