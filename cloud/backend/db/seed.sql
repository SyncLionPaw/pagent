-- Demo seed for local / compose
-- login: admin / 123  (email admin@local)
-- password hash: argon2id of "123"

insert into users (
    id,
    email,
    display_name,
    status,
    email_verified_at
) values (
    'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    'admin@local',
    'admin',
    'active',
    now()
) on conflict (email) do nothing;

insert into user_passwords (
    user_id,
    password_hash,
    password_algo
)
select
    u.id,
    '$argon2id$v=19$m=65536,t=3,p=4$jgQxvy6pQqOOuGP9j7JGYg$t+lfljo7rcAiRqpwM+kb5MRqFXxCe9JSurkMGaz774M',
    'argon2id'
from users u
where u.email = 'admin@local'
on conflict (user_id) do nothing;
