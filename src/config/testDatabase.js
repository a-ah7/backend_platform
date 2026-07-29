const pool = require("./database");

async function testDatabase() {
  try {
    const connection = await pool.getConnection();

    console.log("Database connected successfully");

    const [rows] = await connection.execute(
      "SELECT DATABASE() AS databaseName"
    );

    console.log("Connected database:", rows[0].databaseName);

    connection.release();
    process.exit(0);
  } catch (error) {
    console.error("Database connection failed:");
    console.error(error.message);

    process.exit(1);
  }
}

testDatabase();