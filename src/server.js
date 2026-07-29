require("dotenv").config();

const app = require("./app");

const PORT = process.env.PORT || 3000;

const server = app.listen(PORT, "0.0.0.0", () => {
  console.log("Server running on http://localhost:" + PORT);
  console.log("Network URL: http://192.168.68.106:" + PORT);
});

server.on("error", (error) => {
  console.error("Server error:", error);
});

server.on("close", () => {
  console.log("Server was closed");
});