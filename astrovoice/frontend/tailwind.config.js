/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                space: {
                    900: '#020617',
                    800: '#0f172a',
                    700: '#1e293b',
                },
                galaxy: {
                    primary: '#8b5cf6',
                    secondary: '#d946ef',
                    accent: '#06b6d4',
                }
            }
        },
    },
    plugins: [],
}
