# Demo login credentials

These are the pre-created accounts in `data/users.json`, for testing the
app locally. **Change or remove these before any real deployment** — this
file exists only so you have something to log in with immediately.

| Username         | Password        | Role                 | Departments allowed        | Max confidentiality |
|-------------------|-----------------|----------------------|-----------------------------|----------------------|
| `priya.intern`    | `Intern@123`    | intern               | General                    | Public (0)           |
| `arjun.dev`       | `Employee@123`  | employee             | General, Engineering, Sales| Internal (1)         |
| `sofia.sales`     | `Employee@123`  | employee             | General, Engineering, Sales| Internal (1)         |
| `wei.engmgr`      | `EngMgr@123`    | engineering_manager  | General, Engineering       | Confidential (2)     |
| `aisha.hr`        | `HrMgr@123`     | hr_manager           | General, HR                | Confidential (2)     |
| `carlos.finance`  | `FinMgr@123`    | finance_manager      | General, Finance           | Confidential (2)     |
| `elena.legal`     | `Legal@123`     | legal_counsel        | General, Legal, HR, Finance| Restricted (3)       |
| `james.ceo`       | `Exec@123`      | executive            | All                        | Restricted (3)       |
| `admin.root`      | `Admin@123`     | admin                | All                        | Restricted (3)       |

## Adding your own users

Don't hand-edit `data/users.json` — passwords are stored as salted PBKDF2
hashes, not plaintext. Use the helper script instead:

```bash
python scripts/create_user.py
```

It will prompt for a username, full name, department, role, and password,
and write a properly hashed entry into `data/users.json`. You can also run
it non-interactively:

```bash
python scripts/create_user.py --username jane.doe --full-name "Jane Doe" \
    --department Finance --role finance_manager --password "SomeStrongPass1!"
```

Available roles: `intern`, `employee`, `engineering_manager`, `hr_manager`,
`finance_manager`, `legal_counsel`, `executive`, `admin` (see `src/rbac.py`
to add more).
