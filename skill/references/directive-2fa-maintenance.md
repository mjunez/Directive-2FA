# Mantenimiento del skill directive-2fa (estado 2026-07-20)

## Ambiguedad de nombre RESUELTA
El skill duplicado en `system-administration/directive-2fa/` fue BORRADO el
2026-07-20 (era un borrador obsoleto, no funcional). Queda SOLO este en raiz
(`~/.hermes/skills/directive-2fa/`). La nota de mantenimiento en el SKILL.md body
aun dice "EXISTE SKILL DUPLICADO" — eso YA NO ES CIERTO; ignorar esa linea del body
hasta que se patch-e. Mientras el nombre sea unico, `skill_view(name='directive-2fa')`
carga sin ambiguedad.

## Si `skill_view(name='directive-2fa')` vuelve a dar "Ambiguous skill name"
Hay otra copia suelta en algun subdir de skills/. Borrar la que NO sea la funcional
(esta, ~24KB, con pitfalls 1-22 y componentes 2FA-*). La causa tipica es haber
creado una copia en otra categoria por error de organizacion.
