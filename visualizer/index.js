const express = require('express');

const app = express();

// Root page will render the pages/index, which will be our main lenslet.
app.get('/', (req, res) => {
	res.json({})
});

// Listen on the given port.
app.listen(PORT, () => console.log(`Listening on ${ PORT }`));
