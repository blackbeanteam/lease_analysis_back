import app from './server'

const port = Number(process.env.PORT || 8000)
app.listen(port, () => {
  console.log(`[node-api] listening on :${port}`)
})
