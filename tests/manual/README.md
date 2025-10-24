

# Human-in-the-Loop Testing Suite

This directory contains interactive test scripts that combine automated setup with manual validation steps. These tests verify features that require human judgment, real external services, or visual inspection.

## 🎯 Purpose

Automated tests verify logic, but some features need human validation:
- **OAuth flows** - Real browser interaction with Google/GitHub/Microsoft
- **Email delivery** - Actual inbox verification and formatting checks
- **Stripe payments** - Real checkout flows and webhook handling
- **2FA** - QR code scanning and TOTP verification
- **WebSockets** - Real-time message delivery and connection stability
- **Invitations** - Email delivery and multi-user workflows
- **Sessions** - Multi-device behavior
- **File uploads** - Large file handling and quota enforcement

## 📋 Available Tests

### 1. OAuth Flow Tester (`interactive_oauth_test.py`)
**Purpose:** Test OAuth authentication with real providers

**What it tests:**
- Google, GitHub, Microsoft OAuth flows
- Authorization URL generation
- Callback handling
- Account linking
- User session creation

**Usage:**
```bash
python tests/manual/interactive_oauth_test.py --provider google
python tests/manual/interactive_oauth_test.py --provider github
python tests/manual/interactive_oauth_test.py --provider microsoft
```

**Requirements:**
- OAuth credentials in `.env` file
- Server running on `localhost:8000`
- Web browser access

**Manual steps:**
1. Script generates OAuth URL
2. You open URL in browser
3. Sign in with provider
4. Authorize application
5. Copy callback URL
6. Paste back to script
7. Script validates session

**Time:** ~5 minutes per provider

---

### 2. Email Delivery Tester (`interactive_email_test.py`)
**Purpose:** Test all email functionality

**What it tests:**
- Email verification delivery
- Password reset emails
- Welcome emails
- Notification emails
- Email formatting and quality

**Usage:**
```bash
python tests/manual/interactive_email_test.py --email your@email.com
```

**Requirements:**
- SMTP configured in `.env`
- Access to test email inbox
- Server running

**Manual steps:**
1. Script triggers email send
2. You check your inbox
3. Verify email received
4. Check formatting/content
5. Click links to test
6. Rate email quality

**Time:** ~10 minutes

---

### 3. Stripe Payment Tester
**Purpose:** Test Stripe checkout and webhooks

**Manual Test Procedure:**

#### Setup:
```bash
# 1. Ensure Stripe keys in .env
STRIPE_API_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# 2. Start Stripe CLI webhook forwarding
stripe listen --forward-to localhost:8000/api/v1/stripe/webhook
```

#### Test Checkout:
1. Navigate to: `http://localhost:8000/docs`
2. Find `POST /api/v1/billing/checkout`
3. Execute with test plan ID
4. Click returned checkout URL
5. Use Stripe test card: `4242 4242 4242 4242`
6. Complete checkout
7. Verify webhook received
8. Check subscription created

#### Test Webhooks:
1. Trigger test events via Stripe CLI:
```bash
stripe trigger payment_intent.succeeded
stripe trigger customer.subscription.created
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_succeeded
```

2. Verify events logged in audit logs:
```bash
curl http://localhost:8000/api/v1/audit-logs/search?q=stripe
```

#### Checklist:
- [ ] Checkout session creation
- [ ] Payment page loads
- [ ] Test payment succeeds
- [ ] Webhook received
- [ ] Subscription created
- [ ] User upgraded
- [ ] Invoice generated
- [ ] Payment method saved
- [ ] Cancellation works
- [ ] Refund works

**Time:** ~15-20 minutes

---

### 4. 2FA / TOTP Tester
**Purpose:** Test two-factor authentication

**Manual Test Procedure:**

#### Enable 2FA:
1. Login to your account
2. Navigate to `/api/v1/totp/enable`
3. Scan QR code with authenticator app (Google Authenticator, Authy, etc.)
4. Enter 6-digit code to verify
5. Save backup codes

#### Test 2FA Login:
1. Logout
2. Login with email/password
3. Should prompt for 2FA code
4. Enter code from authenticator app
5. Verify successful login

#### Test Backup Codes:
1. Login without authenticator
2. Use backup code instead
3. Verify it works only once
4. Check backup code marked as used

#### Test 2FA Disable:
1. Disable 2FA with current code
2. Verify can login without 2FA
3. Re-enable and test again

#### Checklist:
- [ ] QR code displays correctly
- [ ] Authenticator app scans QR
- [ ] Setup code works
- [ ] Backup codes generated
- [ ] Login requires 2FA
- [ ] Wrong code rejected
- [ ] Backup codes work
- [ ] Can disable 2FA
- [ ] Account lockout after failures

**Time:** ~10 minutes

---

### 5. WebSocket Real-time Tester
**Purpose:** Test WebSocket connections and real-time messaging

**Manual Test Procedure:**

#### Test Connection:
```python
import asyncio
import websockets
import json

async def test_websocket():
    # Get auth token first
    token = "your_jwt_token"

    uri = f"ws://localhost:8000/api/v1/ws?token={token}"

    async with websockets.connect(uri) as websocket:
        # Receive welcome message
        welcome = await websocket.recv()
        print(f"Connected: {welcome}")

        # Send ping
        await websocket.send(json.dumps({
            "type": "ping",
            "timestamp": "2024-01-01T00:00:00"
        }))

        # Receive pong
        pong = await websocket.recv()
        print(f"Pong: {pong}")

        # Subscribe to notifications
        await websocket.send(json.dumps({
            "type": "subscribe",
            "channel": "notifications"
        }))

        # Keep connection open
        while True:
            message = await websocket.recv()
            print(f"Received: {message}")

asyncio.run(test_websocket())
```

#### Test Scenarios:
1. **Connection**: Verify JWT auth works
2. **Ping/Pong**: Test keep-alive
3. **Subscribe**: Subscribe to channels
4. **Messages**: Send/receive messages
5. **Notifications**: Trigger notification, verify real-time delivery
6. **Disconnect**: Test graceful disconnect
7. **Reconnect**: Test automatic reconnection
8. **Multiple clients**: Open 2+ connections, test broadcast

#### Checklist:
- [ ] Connection with valid token
- [ ] Connection rejected with invalid token
- [ ] Ping/pong works
- [ ] Can subscribe to channels
- [ ] Real-time notifications delivered
- [ ] Messages sent to correct users
- [ ] Graceful disconnect
- [ ] Concurrent connections work
- [ ] Connection limits enforced

**Time:** ~15 minutes

---

### 6. Invitation Flow Tester
**Purpose:** Test organization invitation workflow

**Manual Test Procedure:**

#### Setup:
```bash
# Login as org admin
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}'
```

#### Test Flow:
1. **Send Invitation**:
```bash
curl -X POST http://localhost:8000/api/v1/invitations/organizations/{org_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","expires_in_days":7}'
```

2. **Check Email**: Verify invitation email received

3. **Accept Invitation** (as new user):
```bash
curl -X POST http://localhost:8000/api/v1/invitations/accept \
  -H "Authorization: Bearer $NEW_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"invitation_token_from_email"}'
```

4. **Verify Membership**: Check new user is in org

5. **Test Edge Cases**:
   - Expired invitation
   - Already accepted invitation
   - Invitation to existing member
   - Cancel invitation
   - Resend invitation

#### Checklist:
- [ ] Invitation created
- [ ] Email delivered
- [ ] Email contains correct link/token
- [ ] Can accept invitation
- [ ] User added to organization
- [ ] Cannot accept twice
- [ ] Expired invitations rejected
- [ ] Can cancel invitation
- [ ] Can resend invitation
- [ ] Email updated on resend

**Time:** ~10 minutes

---

### 7. Session Management Tester
**Purpose:** Test multi-device session handling

**Manual Test Procedure:**

#### Test Multi-Device Sessions:
1. **Login from Device 1** (your main browser):
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

2. **Login from Device 2** (incognito/different browser):
   - Use same credentials
   - Should create new session

3. **List Active Sessions**:
```bash
curl http://localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer $TOKEN"
```

4. **Verify Session Info**:
   - Check device info
   - Check IP addresses
   - Check last activity
   - Check login timestamps

5. **Terminate Specific Session**:
```bash
curl -X DELETE http://localhost:8000/api/v1/sessions/{session_id} \
  -H "Authorization: Bearer $TOKEN"
```

6. **Terminate All Other Sessions**:
```bash
curl -X POST http://localhost:8000/api/v1/sessions/terminate-all \
  -H "Authorization: Bearer $TOKEN"
```

#### Checklist:
- [ ] Multiple sessions created
- [ ] Each session tracked separately
- [ ] Device info captured
- [ ] IP addresses logged
- [ ] Can list all sessions
- [ ] Can terminate specific session
- [ ] Can terminate all others
- [ ] Current session remains active
- [ ] Terminated sessions cannot be used

**Time:** ~10 minutes

---

### 8. File Upload & Quota Tester
**Purpose:** Test file upload and quota enforcement

**Manual Test Procedure:**

#### Test File Upload:
```bash
# Upload small file
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt" \
  -F "description=Test file"

# Check quota
curl http://localhost:8000/api/v1/quota \
  -H "Authorization: Bearer $TOKEN"
```

#### Test Large Files:
```python
# Generate large test file
dd if=/dev/zero of=large_file.bin bs=1M count=100  # 100MB

# Upload
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@large_file.bin"
```

#### Test Quota Limits:
1. Check current quota usage
2. Upload files until near limit
3. Try to exceed quota
4. Verify rejection with proper error
5. Delete files
6. Verify quota freed

#### Test File Operations:
1. **Upload**: Various file types (images, PDFs, docs)
2. **Download**: Verify file integrity
3. **List**: Pagination and filtering
4. **Delete**: File removal and quota update
5. **Metadata**: File info and thumbnails

#### Checklist:
- [ ] Can upload small files
- [ ] Can upload large files (up to limit)
- [ ] Quota tracked correctly
- [ ] Quota limit enforced
- [ ] Cannot exceed quota
- [ ] Proper error messages
- [ ] Can download files
- [ ] Downloaded files match uploaded
- [ ] Can delete files
- [ ] Quota freed on delete
- [ ] File metadata correct
- [ ] Concurrent uploads handled

**Time:** ~15 minutes

---

## 🚀 Running All Tests

### Prerequisites:
```bash
# 1. Install dependencies
pip install rich httpx websockets

# 2. Configure environment
cp .env.example .env
# Edit .env with real credentials

# 3. Start server
uvicorn app.main:app --reload

# 4. Start Stripe CLI (for payment tests)
stripe listen --forward-to localhost:8000/api/v1/stripe/webhook
```

### Run Test Suite:
```bash
# OAuth (all providers)
python tests/manual/interactive_oauth_test.py --provider google
python tests/manual/interactive_oauth_test.py --provider github
python tests/manual/interactive_oauth_test.py --provider microsoft

# Email
python tests/manual/interactive_email_test.py --email your@email.com

# Follow manual procedures for:
# - Stripe payments
# - 2FA
# - WebSockets
# - Invitations
# - Sessions
# - File uploads
```

### Total Time: ~2 hours for complete suite

---

## 📊 Test Reports

Each interactive script generates a JSON report:
- `oauth_test_report_YYYYMMDD_HHMMSS.json`
- `email_test_report_YYYYMMDD_HHMMSS.json`

Reports contain:
- Test results (PASS/FAIL/SKIP)
- Timestamps
- Error details
- Manual validation notes

---

## ✅ Success Criteria

A feature passes human-in-the-loop testing when:
1. ✅ All automated setup completes successfully
2. ✅ Manual validation steps are clear and achievable
3. ✅ User experience meets expectations
4. ✅ Edge cases handled gracefully
5. ✅ Error messages are helpful
6. ✅ Visual elements render correctly
7. ✅ External service integrations work

---

## 🐛 Troubleshooting

### Server Connection Issues:
```bash
# Check server is running
curl http://localhost:8000/api/v1/health

# Check logs
tail -f logs/app.log
```

### OAuth Issues:
- Verify OAuth credentials in `.env`
- Check redirect URIs in provider console
- Use incognito mode to avoid cached sessions

### Email Issues:
- Test SMTP connection:
```python
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('user', 'password')
```
- Check spam folder
- Verify sender domain SPF/DKIM

### Stripe Issues:
- Use test mode keys (sk_test_, pk_test_)
- Verify webhook secret matches Stripe CLI
- Check Stripe dashboard for events

---

## 📝 Notes

- **Mock Mode**: Most tests can run in mock mode without real services
- **Test Data**: Use unique emails/data to avoid conflicts
- **Cleanup**: Delete test data after completion
- **Security**: Never commit real credentials
- **Documentation**: Update this README as tests evolve

---

## 🎯 Next Steps

After completing human-in-the-loop tests:
1. Document any issues found
2. Create tickets for improvements
3. Update automated tests based on findings
4. Share results with team
5. Schedule regular re-testing

---

## 📧 Support

Issues or questions:
1. Check automated test suite first: `pytest tests/`
2. Review test documentation: `docs/COMPREHENSIVE_TEST_GUIDE.md`
3. Check API docs: `http://localhost:8000/docs`

