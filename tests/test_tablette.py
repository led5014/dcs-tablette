"""Tests de la tablette : profils d'appareil, lien UDP avec DCS, capture, kneeboards.

Le lien avec DCS est exercé avec de vraies sockets sur la boucle locale :
un faux script Lua reçoit les ordres et envoie les annonces, comme le ferait
`DCS-Tablette-Export.lua`. Les numéros des profils sont recoupés avec les
scripts des modules installés (ou leur copie dans le dépôt) quand ils sont là.
"""
import io
import os
import re
import socket
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tablette import appareils, planche  # noqa: E402
from tablette.appareils import a10c, ah64d, fa18c  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
DCS = Path("C:/Program Files (x86)/Steam/steamapps/common/DCSWorld")
SCRIPT_LUA = RACINE / "dcs_export" / "DCS-Tablette-Export.lua"
LUA_APPAREILS = RACINE / "dcs_export" / "DCS-Tablette-Appareils.lua"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
       b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def scripts_du_module(dossier: str):
    """Scripts cockpit du module installé, ou de sa copie dans le dépôt."""
    for chemin in (DCS / "Mods" / "aircraft" / dossier / "Cockpit" / "Scripts",
                   RACINE / dossier / "Cockpit" / "Scripts"):
        if chemin.is_dir():
            return chemin
    return None


def lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8", errors="replace")


def identifiants(scripts: Path, *noms):
    """Identifiants d'appareil : rang de déclaration dans devices.lua."""
    ordre = re.findall(r'devices\["(\w+)"\]\s*=\s*counter\(\)', lire(scripts / "devices.lua"))
    return {nom: ordre.index(nom) + 1 if nom in ordre else None for nom in noms}


def commandes(scripts: Path, table: str):
    """Numéros d'une table de command_defs.lua remise à start_command."""
    texte = lire(scripts / "command_defs.lua")
    debut = int(re.search(r"start_command\s*=\s*(\d+)", texte).group(1))
    avant, apres = texte.split(f"{table} =", 1)
    assert re.findall(r"count\s*=\s*([^\n]+)", avant)[-1].strip() == "start_command"
    noms = re.findall(r"(\w+)\s*=\s*counter\(\)", apres.split("}", 1)[0])
    return {nom: debut + i + 1 for i, nom in enumerate(noms)}


class TestProfils(unittest.TestCase):
    def test_ddi_du_hornet_dans_le_sens_horaire_depuis_le_bas_a_gauche(self):
        ddi = fa18c.PROFIL.ecran("ddi_gauche")
        attendu = {"1": ("gauche", 4), "5": ("gauche", 0), "6": ("haut", 0),
                   "10": ("haut", 4), "11": ("droite", 0), "15": ("droite", 4),
                   "16": ("bas", 4), "18": ("bas", 2), "20": ("bas", 0)}
        for id_, place in attendu.items():
            b = ddi.bouton(id_)
            self.assertEqual((b.cote, b.rang), place, id_)
        self.assertEqual((ddi.bouton("1").commande, ddi.bouton("20").commande), (3011, 3030))

    def test_mfcd_et_mfd_dans_le_sens_horaire_depuis_le_haut_a_gauche(self):
        for profil in (a10c.PROFIL, appareils.profil_pour("F-16C_50")):
            ecran = profil.ecrans[0]
            places = {b.id: (b.cote, b.rang) for b in ecran.boutons}
            self.assertEqual((places["1"], places["6"], places["11"], places["16"]),
                             (("haut", 0), ("droite", 0), ("bas", 4), ("gauche", 4)), profil.id)
            self.assertEqual(ecran.bouton("20").commande, 3020)

    def test_mpd_de_l_apache(self):
        mpd = ah64d.PROFIL.ecran("mpd_gauche")
        self.assertEqual((mpd.bouton("B1").cote, mpd.bouton("B1").rang), ("bas", 0))
        self.assertEqual((mpd.bouton("L1").cote, mpd.bouton("L1").rang), ("gauche", 0))
        self.assertEqual([mpd.bouton(i).commande for i in ("T1", "R6", "B6", "B1", "L6", "L1")],
                         [3001, 3012, 3013, 3018, 3019, 3024])
        self.assertEqual((mpd.appareil("pilote"), mpd.appareil("cpg")), (42, 44))

    def test_chaque_bouton_a_sa_place_et_son_nom(self):
        for profil in appareils.PROFILS:
            for ecran in profil.ecrans:
                places = [(b.cote, b.rang) for b in ecran.boutons]
                self.assertEqual(len(places), len(set(places)), (profil.id, ecran.id))
                ids = [b.id for b in ecran.boutons]
                self.assertEqual(len(ids), len(set(ids)), (profil.id, ecran.id))
                for b in ecran.boutons:
                    if b.cote != "rangee":
                        self.assertIn(b.cote, appareils.COTES)
                        cote = (ecran.par_cote_y or ecran.par_cote
                                if b.cote in ("gauche", "droite") else ecran.par_cote)
                        self.assertLess(b.rang, cote, (profil.id, b))

    def test_un_appareil_partage_entre_ecrans_sans_numero_commun(self):
        """JF-17 : un seul appareil MFCD pour les trois écrans ; un numéro
        commun appuierait sur deux écrans à la fois."""
        for profil in appareils.PROFILS:
            vus = {}
            for ecran in profil.ecrans:
                for appareil in set(ecran.appareils.values()):
                    commandes = {b.commande for b in ecran.boutons}
                    self.assertEqual(len(commandes), len(ecran.boutons), (profil.id, ecran.id))
                    deja = vus.setdefault(appareil, {})
                    for c in commandes:
                        self.assertNotIn(c, deja, (profil.id, ecran.id, c, deja.get(c)))
                        deja[c] = ecran.id
            if profil.id == "f15e":       # même numérotation, trois appareils : permis
                self.assertEqual(len(vus), 3)

    def test_mpd_du_f15e_dans_le_sens_antihoraire_depuis_le_haut_a_gauche(self):
        mpd = appareils.profil_pour("F-15ESE").ecran("mpd_gauche")
        attendu = {"1": ("gauche", 0), "5": ("gauche", 4), "6": ("bas", 0), "10": ("bas", 4),
                   "11": ("droite", 4), "15": ("droite", 0), "16": ("haut", 4),
                   "20": ("haut", 0)}
        for id_, place in attendu.items():
            self.assertEqual((mpd.bouton(id_).cote, mpd.bouton(id_).rang), place, id_)
        self.assertEqual((mpd.bouton("1").commande, mpd.bouton("20").commande), (3061, 3080))

    def test_mpcd_du_harrier_numerotes_comme_le_hornet(self):
        av8b = appareils.profil_pour("AV8BNA")
        gauche, droit = av8b.ecran("mpcd_gauche"), av8b.ecran("mpcd_droit")
        self.assertEqual((gauche.bouton("1").cote, gauche.bouton("1").rang), ("gauche", 4))
        self.assertEqual((gauche.bouton("20").cote, gauche.bouton("20").rang), ("bas", 0))
        self.assertEqual((gauche.bouton("1").commande, droit.bouton("20").commande), (3200, 3243))
        self.assertEqual((gauche.appareil(""), droit.appareil("")), (26, 27))

    def test_mfcd_du_jf17_en_portrait(self):
        jf17 = appareils.profil_pour("JF-17")
        for ecran in jf17.ecrans:
            self.assertEqual((ecran.par_cote, ecran.par_cote_y), (5, 8))
            self.assertLess(ecran.aspect, 1)
            self.assertEqual(len(ecran.boutons), 26)
            self.assertEqual(ecran.appareil(""), 47)
        gauche = jf17.ecran("mfcd_gauche")
        self.assertEqual([gauche.bouton(i).commande for i in ("U1", "L1", "L8", "R1", "D5")],
                         [3238, 3244, 3251, 3252, 3266])
        d = jf17.description()["ecrans"][0]
        self.assertEqual((d["par_cote"], d["par_cote_y"]), (5, 8))

    def test_abris_du_ka50_et_shkval_sans_bouton(self):
        ka50 = appareils.profil_pour("Ka-50_3")
        self.assertIs(ka50, appareils.profil_pour("Ka-50"))
        self.assertEqual(ka50.ecran("shkval").boutons, ())
        abris = ka50.ecran("abris")
        self.assertEqual([(b.cote, b.commande) for b in abris.boutons],
                         [("rangee", 3001 + i) for i in range(5)])
        lua = appareils.lua_appareils().split('["Ka-50"]')[1].split('\n  },')[0]
        self.assertIn("[9] = { [3001] = true", lua)
        self.assertNotIn("[8] = {", lua)                    # le Shkval n'a rien à recevoir

    def test_profil_choisi_d_apres_le_nom_annonce_par_dcs(self):
        attendu = {"FA-18C_hornet": "fa18c", "F-16C_50": "f16c", "AH-64D_BLK_II": "ah64d",
                   "OH58D": "oh58d", "Mi-24P": "mi24p", "SA342M": "sa342", "SA342Mistral": "sa342",
                   "A-10C_2": "a10c", "MiG-29 Fulcrum": "mig29", "Su-25T": "fc3",
                   "MiG-29G": "fc3_otan", "AV8BNA": "av8b", "F-15ESE": "f15e", "JF-17": "jf17",
                   "Ka-50_3": "ka50", "CH-47Fbl1": "ch47f", "Bf-109K-4": "bf109",
                   "P-51D": "p51d", "P-51D-30-NA": "p51d", "F-86F Sabre": "f86",
                   "MiG-21Bis": "mig21", "Mi-8MT": "mi8", "F-14B": "f14", "L-39ZA": "l39",
                   "Christen Eagle II": "generique", None: "generique"}
        for nom, id_ in attendu.items():
            self.assertEqual(appareils.profil_pour(nom).id, id_, nom)
        noms = [n for p in appareils.PROFILS for n in p.noms_dcs]
        self.assertEqual(len(noms), len(set(noms)))
        ids = [p.id for p in appareils.PROFILS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_zones_d_export_toutes_dans_la_configuration(self):
        from tablette.ecrans_dcs import EXPORTS
        self.assertLessEqual(set(appareils.viewports()), set(EXPORTS))

    def test_le_lua_genere_est_a_jour(self):
        self.assertEqual(lire(LUA_APPAREILS), appareils.lua_appareils(),
                         "relancer scripts/generer_lua_appareils.py")

    def test_la_liste_blanche_ne_mele_pas_les_appareils(self):
        lua = appareils.lua_appareils()
        hornet = lua.split('["FA-18C_hornet"]')[1].split('\n  },')[0]
        apache = lua.split('["AH-64D_BLK_II"]')[1].split('\n  },')[0]
        self.assertIn("[35] = {", hornet)
        self.assertIn("[25] = {", hornet)                     # l'UFC
        self.assertNotIn("[42] = {", hornet)
        self.assertIn("[42] = {", apache)
        self.assertIn("[44] = {", apache)                     # MPD du CPG
        self.assertNotIn("[35] = {", apache)
        self.assertIn("pages = { [68]", hornet)
        f16 = lua.split('["F-16C_50"]')[1].split('\n  },')[0]
        self.assertIn("pages = { }", f16)                     # kneeboard non relevé
        self.assertIn('TABLETTE_APPAREILS', lire(SCRIPT_LUA))
        self.assertIn('DCS-Tablette-Appareils.lua', lire(SCRIPT_LUA))


class TestContreLesScriptsDesModules(unittest.TestCase):
    """Une mise à jour de DCS qui décalerait les listes doit se voir ici."""

    def module(self, dossier):
        scripts = scripts_du_module(dossier)
        if scripts is None:
            self.skipTest(f"module {dossier} absent")
        return scripts

    def nombre(self, texte, nom):
        return float(re.search(rf"\b{nom}\s*=\s*(-?[\d.]+)", texte).group(1))

    def test_reperes_des_libelles_de_l_apache(self):
        s = self.module("AH-64D")
        defs = lire(s / "Displays" / "MFD" / "indicator" / "MFD_PB_Defs.lua")
        self.assertEqual(self.nombre(lire(s / "Displays" / "MFD" / "indicator"
                                          / "MFD_Page_Defs.lua"), "display_size_pix"), 1024)
        self.assertEqual(ah64d.REPERES_X, appareils.reperes(
            self.nombre(defs, "TDXLeftPos"), self.nombre(defs, "TDXRightPos"), 6, 512))
        self.assertEqual(ah64d.REPERES_Y, appareils.reperes(
            self.nombre(defs, "LRYTopPos"), self.nombre(defs, "LRYBottomPos"), 6, 512,
            vers_le_bas=True))

    def test_reperes_des_libelles_du_hornet(self):
        s = self.module("FA-18C")
        dossier = s / "Multipurpose_Display_Group" / "Common" / "indicator"
        defs = lire(dossier / "MPD_PB_defs.lua")
        self.assertEqual(self.nombre(lire(dossier / "MDG_units.lua"), "UnitsPerSide"), 1024)
        x0, pas_x = self.nombre(defs, "TDXLeftPos"), self.nombre(defs, "PB_TextDistBetweenWordsInRow")
        y0 = self.nombre(defs, "LRYLeftPos")
        pas_y = self.nombre(defs, "PB_TextDistBetweenWordsInColumn")
        self.assertEqual(fa18c.REPERES_X, appareils.reperes(x0, x0 + 4 * pas_x, 5, 512))
        self.assertEqual(fa18c.REPERES_Y, appareils.reperes(y0, y0 - 4 * pas_y, 5, 512,
                                                            vers_le_bas=True))

    def test_reperes_des_libelles_de_l_a10c(self):
        from tablette.appareils import a10c
        s = self.module("A-10C_2")
        dossier = s / "MFCD" / "indicator"
        tailles = lire(dossier / "MFCD_sizes.lua")
        self.assertEqual((self.nombre(tailles, "max_pixels_count"),
                          self.nombre(tailles, "size_k")), (569, 0.97))
        osb = lire(dossier / "MFCD_useful_definitions.lua").split("OSB_positions", 1)[1]
        self.assertRegex(osb, r"\[1\]\s*=\s*\{110\s*,")
        self.assertRegex(osb, r"\[2\]\s*=\s*\{110 \+ 87\.25\s*,")
        self.assertRegex(osb, r"\[6\]\s*=\s*\{[^,]+,\s*max_pixels_count - 100\s*\}")
        self.assertRegex(osb, r"\[7\]\s*=\s*\{[^,]+,\s*max_pixels_count - 100 -\s+82\.5\}")
        self.assertAlmostEqual(a10c.REPERES_X[1] - a10c.REPERES_X[0], 87.25 * 0.97 / 569,
                               places=3)

    def test_reperes_sur_l_image_rognee_de_la_tablette(self):
        from tablette.app import vu_par_la_tablette
        from tablette.video import ROGNAGE
        d = vu_par_la_tablette(ah64d.PROFIL.description())
        mpd = d["ecrans"][0]
        self.assertAlmostEqual(mpd["reperes_x"][0],
                               (ah64d.REPERES_X[0] - ROGNAGE) / (1 - 2 * ROGNAGE), places=3)
        self.assertIsNone(d["ecrans"][2]["reperes_x"])                  # TEDAC : pas de boutons
        self.assertEqual(ah64d.PROFIL.description()["ecrans"][0]["reperes_x"],
                         list(ah64d.REPERES_X))                          # le profil n'est pas touché
        # Libellés plus serrés que les boutons répartis : c'est ce qui décalait.
        self.assertGreater(ah64d.REPERES_X[0], 1 / 12 + 0.05)

    def test_hornet(self):
        s = self.module("FA-18C")
        self.assertEqual(identifiants(s, "MDI_LEFT", "MDI_RIGHT", "AMPCD", "KNEEBOARD", "UFC"),
                         {"MDI_LEFT": 35, "MDI_RIGHT": 36, "AMPCD": 37,
                          "KNEEBOARD": fa18c.PROFIL.kneeboard, "UFC": planche.UFC})
        ufc = commandes(s, "UFC_commands")
        self.assertEqual(ufc["KbdSwENT"], planche.TOUCHES_UFC["ENT"])
        self.assertEqual(ufc["FuncSwAP"], planche.TOUCHES_UFC["AP"])
        self.assertEqual(ufc["Comm1Ch"], planche.MOLETTES_UFC["COMM1"])
        texte = lire(s / "command_defs.lua").split("MDI/AMPCD Pushbuttons")[1][:400]
        self.assertRegex(texte, r"count = start_command \+ 10")
        # Les tables des aiguilles, telles que mainpanel_init.lua les déclare.
        panneau = lire(s / "mainpanel_init.lua")
        bloc = panneau.split("Airspeed.arg_number")[1][:400]
        self.assertIn(f"= {planche.BADIN[0]}", bloc.split("\n")[0])
        lampes = lire(s / "MainPanel" / "lamps.lua")
        for nom, lampe in (("MASTER CAUTION", "MASTER_CAUTION"), ("FIRE G", "FIRE_LEFT"),
                           ("NOSE", "NOSE_GEAR"), ("HOOK", "HOOK")):
            motif = rf"create_caution_lamp\({planche.VOYANTS[nom]},\s*CautionLights\.CPT_LTS_{lampe}\)"
            self.assertTrue(re.search(motif, lampes), nom)

    def test_apache(self):
        s = self.module("AH-64D")
        self.assertEqual(identifiants(s, "MFD_PLT_LEFT", "MFD_PLT_RIGHT", "MFD_CPG_LEFT",
                                      "MFD_CPG_RIGHT", "KNEEBOARD"),
                         {"MFD_PLT_LEFT": 42, "MFD_PLT_RIGHT": 43, "MFD_CPG_LEFT": 44,
                          "MFD_CPG_RIGHT": 45, "KNEEBOARD": ah64d.PROFIL.kneeboard})
        mpd = commandes(s, "mpd_commands")
        ecran = ah64d.PROFIL.ecran("mpd_gauche")
        for nom, id_ in (("T1", "T1"), ("B1", "B1"), ("L6", "L6"), ("AC", "A/C"),
                         ("Asterisk", "*"), ("FCR", "FCR")):
            self.assertEqual(mpd[nom], ecran.bouton(id_).commande, nom)

    def test_a10c(self):
        s = self.module("A-10C_2")
        self.assertEqual(identifiants(s, "MFCD_LEFT", "MFCD_RIGHT", "KNEEBOARD"),
                         {"MFCD_LEFT": 2, "MFCD_RIGHT": 3, "KNEEBOARD": None})
        self.assertRegex(lire(s / "command_defs.lua"), r"Button_1\s*=\s*start_command \+ 1;")
        commun = DCS / "Scripts" / "Aircrafts" / "_Common" / "Cockpit" / "KNEEBOARD"
        self.assertIn("devices.KNEEBOARD or 100", lire(commun / "declare_kneeboard_device.lua"))
        self.assertEqual(a10c.PROFIL.kneeboard, 100)

    def test_appareils_sans_ecran(self):
        for dossier, nom in (("MiG-29-Fulcrum", "MiG-29 Fulcrum"), ("TF-51D", "TF-51D"),
                             ("FW-190D9", "FW-190D9")):
            s = scripts_du_module(dossier)
            if s is None:
                continue
            self.assertEqual(identifiants(s, "KNEEBOARD")["KNEEBOARD"],
                             appareils.profil_pour(nom).kneeboard, dossier)

    def test_commandes_de_page_communes(self):
        texte = DCS / "Config" / "Input" / "Aircrafts" / "common_keyboard_binding.lua"
        if not texte.exists():
            self.skipTest("DCS absent")
        texte = lire(texte)
        self.assertRegex(texte, r"down = 3001,\s*cockpit_device_id = kneeboard_id.*Next Page")
        self.assertRegex(texte, r"down = 3002,\s*cockpit_device_id = kneeboard_id.*Previous Page")
        self.assertIn("local kneeboard_id = 100", texte)


class TestPlanche(unittest.TestCase):
    TEXTE_UFC = ("-----------------------------------------\nUFC_MainDummy\n\n"
                 "-----------------------------------------\nUFC_mask\n\n"
                 "-----------------------------------------\nUFC_ScratchPadString1Display\nC\n"
                 "-----------------------------------------\nUFC_ScratchPadNumberDisplay\n"
                 "  127.500\n"
                 "-----------------------------------------\nUFC_OptionCueing1\n:\n"
                 "-----------------------------------------\nUFC_OptionDisplay1\nTR  \n"
                 "-----------------------------------------\nUFC_Comm1Display\n`1\n"
                 "children are {\n}\n")

    def test_texte_des_ecrans_lu_par_champ(self):
        champs = planche.lire_indication(self.TEXTE_UFC)
        self.assertEqual(champs["UFC_ScratchPadNumberDisplay"], "  127.500")
        self.assertEqual(champs["UFC_Comm1Display"], "`1")
        ufc = planche.ufc(champs)
        self.assertEqual(ufc["bloc"], ["C", "", "  127.500"])
        self.assertEqual(ufc["options"][0], {"repere": ":", "texte": "TR"})
        self.assertEqual(ufc["comm1"], "`1")
        self.assertEqual(planche.lire_indication("MENU_1__id:1\nMENU\n"), {"MENU_1": "MENU"})

    def test_aiguilles_lues_avec_les_tables_du_cockpit(self):
        args = {217: 0.586, 225: 0.22, 218: 0.5, 219: 0.3, 220: 1 / 9, 205: 0.5, 206: -0.5,
                242: 0.636, 310: 0.6, 311: 0.6, 13: 1.0, 10: 0.0}
        instr = planche.instruments(args)
        self.assertEqual(instr["badin"]["valeur"], 200.0)
        self.assertEqual(instr["vario"]["valeur"], 500.0)
        self.assertEqual(instr["altimetre"]["valeur"], 13500)
        self.assertEqual((instr["sai"]["assiette"], instr["sai"]["inclinaison"]), (45.0, -90.0))
        self.assertEqual(instr["frein"]["valeur"], 3000.0)
        voyants = planche.voyants(args)
        self.assertTrue(voyants["MASTER CAUTION"])
        self.assertFalse(voyants["FIRE G"])
        self.assertIsNone(planche.instruments({}))

    def test_graduations_placees_avec_les_memes_tables(self):
        cadrans = planche.cadrans()
        badin = {g["texte"]: g["angle"] for g in cadrans["badin"]["graduations"]}
        self.assertAlmostEqual(badin["200"], 0.586 * 360, places=0)
        vario = {g["angle"] for g in cadrans["vario"]["graduations"] if g["texte"] == "0"}
        self.assertEqual(vario, {270.0})


class TestConfigurationEcransDCS(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Config" / "MonitorSetup").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def options(self, choix, largeur=2560, hauteur=1440):
        (self.saved / "Config" / "options.lua").write_text(
            'options = {\n\t["graphics"] = {\n'
            f'\t\t["aspect"] = {largeur / hauteur:.14g},\n'
            f'\t\t["fullScreen"] = false,\n\t\t["height"] = {hauteur},\n'
            f'\t\t["multiMonitorSetup"] = "{choix}",\n\t\t["width"] = {largeur},\n'
            '\t},\n}\n', encoding="utf-8")

    def test_le_fichier_genere_se_relit_a_l_identique(self):
        from tablette.ecrans_dcs import (disposition_essai, disposition_second_ecran,
                                         generer, lire_zones)
        for vue, zones in (((0, 0, 2560, 1440), disposition_essai(2560, 1440)),
                           ((0, 0, 2560, 1440),
                            disposition_second_ecran(2560, 1440, 1920, 1080))):
            texte = generer(vue, zones, "test")
            texte.encode("ascii")
            self.assertEqual(lire_zones(texte, 4480, 1440), zones)

    def test_apostrophe_echappee_dans_les_chaines_lua(self):
        from tablette.ecrans_dcs import generer
        texte = generer((0, 0, 100, 100), {}, "Vue sur l'ecran principal")
        self.assertIn(r"Description = 'Vue sur l\'ecran principal'", texte)
        # Chaque ligne a un nombre pair d'apostrophes non échappées.
        for ligne in texte.splitlines():
            self.assertEqual(ligne.replace(r"\'", "").count("'") % 2, 0, ligne)

    def test_dispositions(self):
        from tablette.ecrans_dcs import disposition_essai, disposition_second_ecran
        self.assertEqual(disposition_essai(2560, 1440),
                         {"LEFT_MFCD": (0, 960, 480, 480), "CENTER_MFCD": (800, 960, 480, 480),
                          "TEDAC": (1280, 960, 480, 480), "RIGHT_MFCD": (2080, 960, 480, 480)})
        # Écran virtuel 2560 × 1440 : gauche et droit en haut, central et TEDAC
        # dessous, coin bas droit laissé au kneeboard.
        self.assertEqual(disposition_second_ecran(2560, 1440, 2560, 1440),
                         {"LEFT_MFCD": (2560, 0, 720, 720), "RIGHT_MFCD": (3280, 0, 720, 720),
                          "CENTER_MFCD": (2560, 720, 720, 720), "TEDAC": (3280, 720, 720, 720)})

    def test_dcs_regle_dans_options_lua_avec_une_copie(self):
        from tablette.ecrans_dcs import regler_options
        self.options("1camera")
        copie = regler_options(self.saved, 5120, 1440)
        texte = lire(self.saved / "Config" / "options.lua")
        for attendu in ('["multiMonitorSetup"] = "tablette",', '["width"] = 5120,',
                        '["height"] = 1440,', '["fullScreen"] = false,',
                        '["aspect"] = 3.5555555555556,'):
            self.assertIn(attendu, texte)
        self.assertIn('"1camera"', lire(copie))

    def test_le_kneeboard_ne_recouvre_aucun_ecran(self):
        """Mesuré en vrai le 25/10/2026 en 5120 × 1440 : cadre du kneeboard de
        x = 4368 à 5120 et de y = 356 à 1440, page 720 × 1080."""
        from tablette.ecrans_dcs import (BANDEAU_KNEEBOARD, disposition_second_ecran,
                                         zone_kneeboard)
        self.assertEqual(zone_kneeboard(5120, 1440), (4400, 356, 720, 1084))
        self.assertEqual(zone_kneeboard(2560, 1440), (1840, 356, 720, 1084))
        for principal, second in (((2560, 1440), (2560, 1440)), ((2560, 1440), (1920, 1080)),
                                  ((1920, 1080), (1920, 1080))):
            largeur_totale = principal[0] + second[0]
            kx, ky, kl, kh = zone_kneeboard(largeur_totale, max(principal[1], second[1]))
            cadre = (kx - BANDEAU_KNEEBOARD, ky, kl + BANDEAU_KNEEBOARD, kh)
            for nom, (x, y, l, h) in disposition_second_ecran(*principal, *second).items():
                separes = (x + l <= cadre[0] or cadre[0] + cadre[2] <= x
                           or y + h <= cadre[1] or cadre[1] + cadre[3] <= y)
                self.assertTrue(separes, (principal, second, nom))
                self.assertGreaterEqual(x, principal[0], nom)        # sur le second
                self.assertLessEqual(x + l, largeur_totale, nom)


    def test_expressions_des_fichiers_livres_avec_dcs(self):
        from tablette.ecrans_dcs import lire_zones
        texte = ("LEFT_MFCD =\n{\n     x = 0;\n     y = 0;\n     width = screen.width / 3;\n"
                 "     height = screen.height;\n}\nRIGHT_MFCD =\n{\n"
                 "     x = screen.width *(2 / 3);\n     y = 0;\n"
                 "     width = screen.width / 3;\n     height = screen.height;\n}\n")
        self.assertEqual(lire_zones(texte, 3840, 1080),
                         {"LEFT_MFCD": (0, 0, 1280, 1080), "RIGHT_MFCD": (2560, 0, 1280, 1080)})
        self.assertEqual(lire_zones("LEFT_MFCD = { x = os.exit(); y = 0; width = 1; "
                                    "height = 1; }", 100, 100), {})

    def test_configuration_choisie_dans_dcs(self):
        from tablette.ecrans_dcs import (NOM_FICHIER, PasDExport, disposition_essai,
                                         generer, zones_actives)
        zones = disposition_essai(2560, 1440)
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), zones, "test"), encoding="ascii")
        self.options("tablette")
        self.assertEqual(zones_actives(self.saved), zones)
        self.options("Tablette DCS")       # désignée par son nom affiché
        self.assertEqual(zones_actives(self.saved), zones)
        self.options("1camera")
        with self.assertRaises(PasDExport) as e:
            zones_actives(self.saved)
        self.assertIn("Tablette DCS", str(e.exception))

    def test_la_copie_d_origine_survit_a_une_seconde_installation(self):
        from tablette.ecrans_dcs import regler_options, retablir_options
        self.options("1camera", 1920, 1080)
        regler_options(self.saved, 5120, 1440)
        copie = regler_options(self.saved, 4480, 1440)
        self.assertIn('"1camera"', lire(copie))
        # Un réglage changé depuis reste ; l'affichage revient seul.
        options = self.saved / "Config" / "options.lua"
        options.write_text(lire(options).replace('["graphics"] = {',
                                                 '["graphics"] = {\n\t\t["vsync"] = true,'),
                           encoding="utf-8")
        retablir_options(self.saved)
        texte = lire(options)
        for attendu in ('["multiMonitorSetup"] = "1camera",', '["width"] = 1920,',
                        '["height"] = 1080,', '["vsync"] = true,'):
            self.assertIn(attendu, texte)


class TestInstallation(unittest.TestCase):
    """Ce que fait `DCS-Tablette.exe installer` / `desinstaller`, dans un faux
    Saved Games/DCS : jamais celui du poste."""

    PRINCIPAL = (0, 0, 2560, 1440, True)
    VIRTUEL = (2560, 0, 2560, 1440, False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Scripts").mkdir()
        (self.saved / "Config").mkdir()
        (self.saved / "Config" / "options.lua").write_text(
            'options = {\n\t["graphics"] = {\n\t\t["aspect"] = 1.7777777777778,\n'
            '\t\t["fullScreen"] = true,\n\t\t["height"] = 1440,\n'
            '\t\t["multiMonitorSetup"] = "1camera",\n\t\t["width"] = 2560,\n\t},\n}\n',
            encoding="utf-8")
        self.export = self.saved / "Scripts" / "Export.lua"
        # Un Export.lua d'un autre outil, pas en UTF-8 et sans fin de ligne.
        self.export.write_bytes(b"dofile(lfs.writedir()..'Scripts/TacviewGameExport.lua') -- \xe9")

    def tearDown(self):
        self.tmp.cleanup()

    def test_scripts_installes_une_fois_puis_retires(self):
        from tablette.installation import (LIGNE, SCRIPTS, desinstaller_scripts, est_installe,
                                           installer_scripts)
        origine = self.export.read_bytes()
        self.assertFalse(est_installe(self.saved))
        installer_scripts(self.saved)
        lignes = installer_scripts(self.saved)
        self.assertIn("Export.lua charge déjà la tablette.", lignes)
        self.assertTrue(est_installe(self.saved))
        texte = self.export.read_bytes()
        self.assertTrue(texte.startswith(origine + b"\n"))
        self.assertEqual(texte.count(LIGNE.encode()), 1)
        for nom in SCRIPTS:
            self.assertEqual((self.saved / "Scripts" / nom).read_bytes(),
                             (RACINE / "dcs_export" / nom).read_bytes())
        self.assertEqual(len(list((self.saved / "Scripts").glob("Export.lua.avant-tablette-*"))), 1)

        desinstaller_scripts(self.saved)
        self.assertEqual(self.export.read_bytes(), origine + b"\n")
        self.assertFalse(est_installe(self.saved))
        for nom in SCRIPTS:
            self.assertFalse((self.saved / "Scripts" / nom).exists())

    def test_ecrans_sur_l_ecran_virtuel_puis_retires(self):
        from tablette.ecrans_dcs import NOM_FICHIER, options_affichage, zones_actives
        from tablette.installation import configurer_ecrans, retirer_ecrans
        complet, _ = configurer_ecrans(self.saved, ecrans=[self.PRINCIPAL, self.VIRTUEL],
                                       ouvert=lambda: False)
        self.assertTrue(complet)
        self.assertEqual(options_affichage(self.saved), ("tablette", 5120, 1440))
        self.assertEqual(zones_actives(self.saved)["LEFT_MFCD"], (2560, 0, 720, 720))

        self.assertIn("DCS est ouvert", retirer_ecrans(self.saved, ouvert=lambda: True)[0])
        retirer_ecrans(self.saved, ouvert=lambda: False)
        self.assertEqual(options_affichage(self.saved), ("1camera", 2560, 1440))
        self.assertIn('["fullScreen"] = true,', lire(self.saved / "Config" / "options.lua"))
        self.assertFalse((self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).exists())

    def test_sans_second_ecran_rien_n_est_ecrit(self):
        from tablette.installation import configurer_ecrans
        # Un écran à gauche du principal ne convient pas : DCS s'étend vers la droite.
        a_gauche = (-1920, 0, 1920, 1080, False)
        for ecrans in ([self.PRINCIPAL], [self.PRINCIPAL, a_gauche]):
            complet, lignes = configurer_ecrans(self.saved, ecrans=ecrans, ouvert=lambda: False)
            self.assertFalse(complet)
            self.assertIn("Virtual Display Driver", "\n".join(lignes))
        self.assertFalse((self.saved / "Config" / "MonitorSetup").exists())
        self.assertIn('"1camera"', lire(self.saved / "Config" / "options.lua"))

    @unittest.skipUnless(sys.platform == "win32", "raccourci Windows")
    def test_raccourci_vers_l_executable(self):
        from tablette.installation import RACCOURCI, creer_raccourci
        lien = creer_raccourci(Path(sys.executable), self.saved)
        self.assertEqual(lien, self.saved / RACCOURCI)
        self.assertTrue(lien.read_bytes().startswith(b"L\x00\x00\x00"))   # en-tête d'un .lnk

    def test_mise_a_jour_dcs_ouvert_configuration_identique_intacte(self):
        """Réécrite DCS ouvert, la configuration paraîtrait changée depuis son
        lancement et la tablette ne capturerait plus rien."""
        from tablette.ecrans_dcs import NOM_FICHIER
        from tablette.installation import configurer_ecrans
        ecrans = [self.PRINCIPAL, self.VIRTUEL]
        configurer_ecrans(self.saved, ecrans=ecrans, ouvert=lambda: False)
        fichier = self.saved / "Config" / "MonitorSetup" / NOM_FICHIER
        avant = fichier.stat().st_mtime_ns
        complet, lignes = configurer_ecrans(self.saved, ecrans=ecrans, ouvert=lambda: True)
        self.assertTrue(complet)
        self.assertTrue(lignes[0].startswith("Inchangé"))
        self.assertTrue(lignes[-1].startswith("DCS déjà réglé"))   # pas de « relance DCS »
        self.assertEqual(fichier.stat().st_mtime_ns, avant)
        self.assertFalse(fichier.with_suffix(".lua.precedent").exists())

    def test_dcs_ouvert_options_lua_intact(self):
        from tablette.installation import configurer_ecrans
        avant = lire(self.saved / "Config" / "options.lua")
        complet, lignes = configurer_ecrans(self.saved, ecrans=[self.PRINCIPAL, self.VIRTUEL],
                                            ouvert=lambda: True)
        self.assertTrue(complet)
        self.assertEqual(lire(self.saved / "Config" / "options.lua"), avant)
        self.assertIn("5120×1440", "\n".join(lignes))

    def installer(self, reponses, ouvert, pret=True):
        """`installer` sans console ni écrans réels : réponses et état de DCS
        joués d'avance. Rend le code de sortie et ce qui s'est affiché."""
        import contextlib
        import io
        from unittest import mock

        from tablette import installation
        reponses = list(reponses)
        sortie = io.StringIO()
        self.chemin_choix = self.saved / "installation.json"

        def demander(question):
            print(question)
            return reponses.pop(0)

        ecrans = [ecran("\\\\.\\DISPLAY1", "AMD Radeon", "PCI", 0, 0, principal=True), ecran()]
        with mock.patch("tablette.ecran_virtuel.preparer", return_value=pret) as preparer, \
                contextlib.redirect_stdout(sortie):
            code = installation.installer(self.saved, demander=demander, ouvert=ouvert,
                                          lister_ecrans=lambda: ecrans,
                                          chemin_choix=self.chemin_choix)
        self.preparer_appele = preparer.called
        return code, sortie.getvalue()

    def choix(self):
        from tablette.installation import lire_choix
        return lire_choix(self.chemin_choix)

    def test_installer_attend_que_dcs_soit_ferme(self):
        etats = [True, True, False, False]
        code, sortie = self.installer(["", ""], lambda: etats.pop(0))
        self.assertEqual(code, 0)
        self.assertEqual(etats, [])                 # deux fois ouvert, puis fermé
        self.assertEqual(sortie.count("DCS est ouvert"), 2)
        self.assertIn('"tablette"', lire(self.saved / "Config" / "options.lua"))
        self.assertEqual(self.choix(), {"mode": "second_ecran", "physique": False})

    def test_installer_montre_les_ecrans_et_dcs_avant_tout(self):
        _, sortie = self.installer([], lambda: False)
        self.assertIn("Vos écrans :", sortie)
        self.assertIn("— virtuel — à droite du principal", sortie)
        self.assertIn("DCS : configuration « 1camera », 2560×1440, plein écran", sortie)

    def test_installer_dcs_laisse_ouvert_dit_quoi_regler(self):
        avant = lire(self.saved / "Config" / "options.lua")
        code, sortie = self.installer(["p"], lambda: True)
        self.assertEqual(code, 0)
        self.assertEqual(lire(self.saved / "Config" / "options.lua"), avant)
        self.assertIn("Options → Système → Moniteurs", sortie)

    def test_installer_sans_ecran_virtuel_ne_touche_pas_a_dcs(self):
        avant = lire(self.saved / "Config" / "options.lua")
        code, sortie = self.installer(["n"], lambda: False, pret=None)
        self.assertEqual(code, 1)
        self.assertTrue((self.saved / "Scripts" / "DCS-Tablette-Export.lua").exists())
        self.assertEqual(lire(self.saved / "Config" / "options.lua"), avant)
        self.assertIn("À la main", sortie)

    def test_installer_sans_ecran_propose_le_mode_essai(self):
        from tablette.ecrans_dcs import zones_actives
        code, sortie = self.installer(["o"], lambda: False, pret=None)
        self.assertEqual(code, 0)
        self.assertEqual(self.choix()["mode"], "essai")
        for x, y, l, h in zones_actives(self.saved).values():
            self.assertLessEqual(x + l, 2560)        # sur l'écran principal

    def test_installer_garde_la_configuration_du_pilote(self):
        """Ses vrais MFD (ou Helios) exportent déjà : on ne remplace rien."""
        options = self.saved / "Config" / "options.lua"
        options.write_text(lire(options).replace('"1camera"', '"Mes MFD"'), encoding="utf-8")
        (self.saved / "Config" / "MonitorSetup").mkdir()
        (self.saved / "Config" / "MonitorSetup" / "mesmfd.lua").write_text(
            "_ = function(p) return p; end;\nname = _('Mes MFD');\n"
            "LEFT_MFCD =\n{\n     x = 2560;\n     y = 0;\n     width = 600;\n     height = 600;\n}\n",
            encoding="utf-8")
        avant = lire(options)
        code, sortie = self.installer([""], lambda: False)
        self.assertEqual(code, 0)
        self.assertIn("votre configuration « Mes MFD » : LEFT_MFCD", sortie)
        self.assertFalse(self.preparer_appele)
        self.assertEqual(lire(options), avant)
        self.assertEqual(self.choix(), {"mode": "existante", "configuration": "Mes MFD"})
        self.assertFalse((self.saved / "Config" / "MonitorSetup" / "tablette.lua").exists())

    def test_installer_ecran_reel_donne_par_le_pilote(self):
        self.installer([""], lambda: False, pret="physique")
        self.assertEqual(self.choix(), {"mode": "second_ecran", "physique": True})


def ecran(nom="\\\\.\\DISPLAY2", carte="Virtual Display Driver",
          ident="Root\\MttVDD MONITOR\\MTT1337\\{4d36e96e}\\0000", x=2560, y=0, largeur=2560,
          hauteur=1440, frequence=240, principal=False, actif=True, modes=()):
    from tablette.ecran_virtuel import Ecran
    return Ecran(nom, carte, ident, x, y, largeur, hauteur, frequence, principal, actif,
                 tuple(modes))


# Relevés sur le poste de développement le 30/10/2026 (EnumDisplayDevices).
PRINCIPAL = ecran("\\\\.\\DISPLAY1", "AMD Radeon RX 9070 XT",
                  "PCI\\VEN_1002&DEV_7550 MONITOR\\CND3CFA\\{4d36e96e}", 0, 0, principal=True)
MODES_VDD = ((1920, 1080, 60), (1920, 1080, 240), (2560, 1440, 60), (2560, 1440, 240),
             (3840, 2160, 60))


class TestEcranVirtuel(unittest.TestCase):
    """Trouver, installer et placer l'écran virtuel, sur des écrans décrits :
    jamais ceux du poste, rien n'est installé ni déplacé."""

    def test_l_ecran_virtuel_est_reconnu_et_pas_la_carte_graphique(self):
        self.assertTrue(ecran().virtuel)
        # Virtual Desktop (VR), Parsec : écrans du pilote, jamais pris pour le nôtre.
        self.assertFalse(ecran(carte="Parsec Virtual Display Adapter", ident="").virtuel)
        self.assertFalse(ecran(carte="Virtual Desktop Monitor", ident="ROOT\\VDM").virtuel)
        self.assertFalse(PRINCIPAL.virtuel)
        self.assertFalse(ecran(carte="Generic PnP Monitor", ident="PCI\\VEN_10DE").virtuel)

    def test_ecran_virtuel_mal_place_va_a_droite_aligne_en_haut(self):
        from tablette.ecran_virtuel import planifier
        for x, y in ((-1920, 300), (2560, 200), (0, 1440)):
            p, lignes = planifier([PRINCIPAL, ecran(x=x, y=y, largeur=1920, hauteur=1080,
                                                    frequence=60, modes=MODES_VDD)])
            self.assertEqual((p.x, p.y, p.largeur, p.hauteur, p.frequence),
                             (2560, 0, 2560, 1440, 240), (x, y))
            self.assertTrue(p.a_faire)
            self.assertEqual(lignes, [])

    def test_ecran_virtuel_deja_en_place(self):
        from tablette.ecran_virtuel import planifier
        p, _ = planifier([PRINCIPAL, ecran(modes=MODES_VDD)])
        self.assertFalse(p.a_faire)
        p, _ = planifier([PRINCIPAL, ecran(actif=False, modes=MODES_VDD)])
        self.assertTrue(p.a_faire)                 # dupliqué : à remettre sur le bureau

    def test_mode_le_plus_proche_de_l_ecran_principal(self):
        from tablette.ecran_virtuel import choisir_mode
        self.assertEqual(choisir_mode(MODES_VDD, 2560, 1440, 240), (2560, 1440, 240))
        self.assertEqual(choisir_mode(MODES_VDD, 2560, 1440, 144), (2560, 1440, 240))
        # Écran large absent : même hauteur d'abord.
        self.assertEqual(choisir_mode(MODES_VDD, 3440, 1440, 60), (2560, 1440, 60))
        # Hauteur absente : moins haut plutôt que plus haut, jamais dessiné.
        self.assertEqual(choisir_mode(MODES_VDD, 2560, 1600, 60), (2560, 1440, 60))
        self.assertIsNone(choisir_mode((), 2560, 1440, 60))

    def test_un_ecran_reel_a_droite_l_ecran_virtuel_va_dessous(self):
        """Le cas courant de deux vrais écrans côte à côte."""
        from tablette.ecran_virtuel import planifier
        physique = ecran("\\\\.\\DISPLAY3", "Generic PnP Monitor", "PCI\\VEN_1002", 2560, 0,
                         1920, 1080, 60)
        p, lignes = planifier([PRINCIPAL, physique, ecran(x=-2560, modes=MODES_VDD)])
        self.assertEqual((p.x, p.y, p.largeur, p.hauteur, p.cote),
                         (0, 1440, 2560, 1440, "dessous"), lignes)
        # À gauche ou au-dessus, il ne gêne pas : l'écran virtuel va à droite.
        for x, y in ((-1920, 0), (0, -1080)):
            p, _ = planifier([PRINCIPAL, ecran(x=x, y=y, largeur=1920, hauteur=1080,
                                               carte="Generic PnP Monitor", ident="PCI"),
                              ecran(x=0, y=1440, modes=MODES_VDD)])
            self.assertEqual((p.x, p.y, p.cote), (2560, 0, "droite"))

    def test_droite_et_dessous_pris_on_dit_lesquels(self):
        from tablette.ecran_virtuel import planifier
        droite = ecran("\\\\.\\DISPLAY3", "Dell", "PCI", 2560, 0, 1920, 1080, 60)
        dessous = ecran("\\\\.\\DISPLAY4", "Tactile", "PCI", 0, 1440, 1920, 1080, 60)
        p, lignes = planifier([PRINCIPAL, droite, dessous, ecran(x=-2560, modes=MODES_VDD)])
        self.assertIsNone(p)
        texte = " ".join(lignes)
        self.assertIn("Dell", texte)
        self.assertIn("Tactile", texte)
        self.assertIn("--essai", texte)

    def test_la_fenetre_de_dcs_ne_couvre_jamais_un_autre_ecran(self):
        """Un écran réel sous le principal ET un écran virtuel plus haut que le
        principal à droite : la fenêtre de DCS (5120 × 1600) mordrait sur le
        réel ; le virtuel est ramené à la hauteur du principal."""
        from tablette.ecran_virtuel import planifier
        dessous = ecran("\\\\.\\DISPLAY4", "Tactile", "PCI", 0, 1440, 1920, 1080, 60)
        p, _ = planifier([PRINCIPAL, dessous,
                          ecran(largeur=2560, hauteur=1600, modes=MODES_VDD + ((2560, 1600, 60),))])
        self.assertEqual((p.x, p.y, p.hauteur), (2560, 0, 1440))

    def test_dessous_la_largeur_compte(self):
        """Principal 3440 × 1440 et écran virtuel sans ce mode : dessous, on
        garde la largeur (une fenêtre plus large qu'eux tomberait à côté)."""
        from tablette.ecran_virtuel import choisir_mode
        modes = ((2560, 1440, 60), (3440, 1080, 60), (3840, 2160, 60))
        self.assertEqual(choisir_mode(modes, 3440, 1440, 60, "droite"), (2560, 1440, 60))
        self.assertEqual(choisir_mode(modes, 3440, 1440, 60, "dessous"), (3440, 1080, 60))

    def test_remis_dessous_dit_ou(self):
        from tablette.ecran_virtuel import remettre
        reel = ecran("\\\\.\\DISPLAY3", "Dell", "PCI", 2560, 0, 1920, 1080, 60)
        listes = [[PRINCIPAL, reel, ecran(x=-2560, modes=MODES_VDD)]] * 2 + [
            [PRINCIPAL, reel, ecran(x=0, y=1440, modes=MODES_VDD)]]
        etat, detail, _ = remettre(True, lister=lambda: listes.pop(0) if len(listes) > 1
                                   else listes[0], etendre=lambda: True,
                                   appliquer=lambda p: None, attendre=lambda s: None)
        self.assertEqual(etat, "repare")
        self.assertIn("placé", detail)
        self.assertIn("sous le principal", detail)

    def test_supports_jamais_un_ecran_reel_sans_accord(self):
        from tablette.installation import supports, support_ecrans
        principal = (0, 0, 2560, 1440, True, False)
        reel_droite = (2560, 0, 1920, 1080, False, False)
        virtuel_dessous = (0, 1440, 2560, 1440, False, True)
        self.assertEqual([t[1] for t in supports([principal, reel_droite], physique=False)], [])
        self.assertEqual([t[1] for t in supports([principal, reel_droite], physique=True)],
                         ["droite"])
        self.assertEqual(support_ecrans([principal, reel_droite, virtuel_dessous], False, False),
                         ((0, 1440, 2560, 1440), (2560, 2880)))
        # Inconnu (relevé sans le savoir, versions d'avant) : pris, comme avant.
        self.assertEqual(support_ecrans([principal[:5], reel_droite[:5]], False),
                         ((2560, 0, 1920, 1080), (4480, 1440)))

    def test_ecrans_du_cockpit_sous_le_principal(self):
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.installation import configurer_ecrans
        from tablette.ecrans_dcs import options_affichage, zones_actives
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        saved = Path(tmp.name)
        (saved / "Config").mkdir()
        (saved / "Config" / "options.lua").write_text(
            '\t\t["aspect"] = 1.7777777777778,\n\t\t["fullScreen"] = true,\n'
            '\t\t["height"] = 1440,\n\t\t["multiMonitorSetup"] = "1camera",\n'
            '\t\t["width"] = 2560,\n', encoding="utf-8")
        ecrans = [(0, 0, 2560, 1440, True, False), (2560, 0, 1920, 1080, False, False),
                  (0, 1440, 2560, 1440, False, True)]
        complet, lignes = configurer_ecrans(saved, ecrans=ecrans, ouvert=lambda: False,
                                            physique=False)
        self.assertTrue(complet, lignes)
        self.assertEqual(options_affichage(saved), ("tablette", 2560, 2880))
        kx, ky, kl, kh = zone_kneeboard(2560, 2880)
        for nom, (x, y, l, h) in zones_actives(saved).items():
            self.assertTrue(y >= 1440 and y + h <= 2880 and x + l <= 2560, nom)   # sur le virtuel
            self.assertLessEqual(x + l, kx - 32, nom)                           # pas sous le kneeboard

    def test_ecran_principal_virtuel(self):
        from tablette.ecran_virtuel import planifier
        p, lignes = planifier([ecran(x=0, principal=True),
                               ecran("\\\\.\\DISPLAY1", "AMD Radeon RX 9070 XT", "PCI", 2560, 0)])
        self.assertIsNone(p)
        self.assertIn("En faire mon écran principal", "\n".join(lignes))

    def test_reglages_du_pilote_completes_sans_rien_retirer(self):
        from xml.etree import ElementTree

        from tablette.ecran_virtuel import reglages_vdd
        livre = ("<?xml version='1.0' encoding='utf-8'?>\n<vdd_settings>\n"
                 "<monitors><count>1</count></monitors>\n<global>\n"
                 "<!--refresh rates-->\n<g_refresh_rate>60</g_refresh_rate>\n"
                 "<g_refresh_rate>244</g_refresh_rate>\n</global>\n<resolutions>\n"
                 "<resolution><width>2560</width><height>1440</height>"
                 "<refresh_rate>30</refresh_rate></resolution>\n</resolutions>\n"
                 "<options><HardwareCursor>true</HardwareCursor></options>\n</vdd_settings>\n")
        texte = reglages_vdd(livre, 3440, 1440, 240)
        racine = ElementTree.fromstring(texte)
        self.assertEqual([g.text for g in racine.iter("g_refresh_rate")], ["60", "244", "240"])
        self.assertEqual([(r.findtext("width"), r.findtext("height"))
                          for r in racine.iter("resolution")],
                         [("2560", "1440"), ("3440", "1440")])
        self.assertEqual(racine.findtext("monitors/count"), "1")
        self.assertEqual(racine.findtext("options/HardwareCursor"), "true")
        self.assertIn("<!--refresh rates-->", texte)
        self.assertEqual(reglages_vdd(texte, 3440, 1440, 240), texte)      # une seule fois
        self.assertEqual(reglages_vdd(livre, 2560, 1440, 60).count("<resolution>"), 1)

    def preparer(self, listes, reponse="", code=0, refus=None):
        """`preparer` avec des écrans joués d'avance : `listes` est ce que
        Windows rend à chaque relevé, la dernière se répète."""
        from tablette.ecran_virtuel import preparer
        listes, appels = list(listes), {"installer": [], "appliquer": [], "etendre": 0}
        lignes = []

        def lister():
            return listes.pop(0) if len(listes) > 1 else listes[0]

        def installer(mode):
            appels["installer"].append(mode)
            return code, ["journal du pilote"]

        def appliquer(p):
            appels["appliquer"].append((p.x, p.y, p.largeur, p.hauteur, p.frequence))
            return refus

        def etendre():
            appels["etendre"] += 1
            return True

        pret = preparer(lignes.append, lambda q: reponse, lister=lister, etendre=etendre,
                        appliquer=appliquer, installer=installer, attendre=lambda s: None)
        return pret, appels, "\n".join(lignes)

    def test_sans_ecran_virtuel_et_sans_accord_rien_n_est_installe(self):
        for reponse in ("n", None):                 # refus, ou pas de console
            pret, appels, texte = self.preparer([[PRINCIPAL]], reponse=reponse)
            self.assertFalse(pret)
            self.assertEqual(appels["installer"], [])
            self.assertIn("Virtual Display Driver", texte)
            self.assertIn("À la main", texte)

    def test_installe_puis_place_au_mode_du_principal(self):
        place = ecran(modes=MODES_VDD)
        pret, appels, texte = self.preparer(
            [[PRINCIPAL], [PRINCIPAL], [PRINCIPAL, ecran(x=-1920, largeur=1920, hauteur=1080,
                                                         frequence=60, modes=MODES_VDD)],
             [PRINCIPAL, place]])
        self.assertTrue(pret, texte)
        self.assertEqual(appels["installer"], [(2560, 1440, 240)])
        self.assertEqual(appels["appliquer"], [(2560, 0, 2560, 1440, 240)])
        self.assertIn("journal du pilote", texte)
        self.assertIn("placé", texte)

    def test_installation_ratee_dit_quoi_faire_a_la_main(self):
        from tablette.ecran_virtuel import REFUS_UAC
        pret, appels, texte = self.preparer([[PRINCIPAL]], code=REFUS_UAC)
        self.assertFalse(pret)
        self.assertEqual(appels["appliquer"], [])
        self.assertIn("À la main", texte)

    def test_pilote_installe_mais_pas_d_ecran(self):
        pret, _, texte = self.preparer([[PRINCIPAL]])
        self.assertFalse(pret)
        self.assertIn("Redémarrer le PC", texte)

    def test_ecran_duplique_remis_en_etendu(self):
        pret, appels, _ = self.preparer(
            [[PRINCIPAL, ecran(actif=False, x=0, y=0, largeur=0, hauteur=0, modes=MODES_VDD)],
             [PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)], [PRINCIPAL, ecran(modes=MODES_VDD)]])
        self.assertTrue(pret)
        self.assertEqual(appels["etendre"], 1)
        self.assertEqual(appels["appliquer"], [(2560, 0, 2560, 1440, 240)])

    def test_deja_en_place_rien_ne_bouge(self):
        pret, appels, texte = self.preparer([[PRINCIPAL, ecran(modes=MODES_VDD)]])
        self.assertTrue(pret)
        self.assertEqual((appels["installer"], appels["appliquer"], appels["etendre"]),
                         ([], [], 0))
        self.assertIn("déjà en place", texte)

    def test_un_ecran_reel_a_droite_n_est_pris_qu_avec_l_accord_du_pilote(self):
        factice = ecran(carte="Generic PnP Monitor", ident="PCI\\VEN_1002", largeur=1920,
                        hauteur=1080, frequence=60)
        pret, appels, texte = self.preparer([[PRINCIPAL, factice]], reponse="o")
        self.assertEqual(pret, "physique")
        self.assertEqual(appels["installer"], [])
        self.assertIn("personne ne le regarde", texte)
        # Entrée seule : c'est non, l'écran reste au pilote et on propose l'écran virtuel.
        pret, appels, texte = self.preparer([[PRINCIPAL, factice]], reponse="")
        self.assertEqual(appels["installer"], [(2560, 1440, 240)])
        self.assertIn("Cet écran reste à vous", texte)

    def test_windows_refuse_le_placement(self):
        pret, _, texte = self.preparer([[PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)]],
                                       refus="Windows refuse ce réglage (code -2)")
        self.assertFalse(pret)
        self.assertIn("Paramètres → Système → Écran", texte)

    def test_placement_non_garde_par_windows(self):
        pret, _, texte = self.preparer([[PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)]])
        self.assertFalse(pret)
        self.assertIn("pas gardé", texte)


class TestVideo(unittest.TestCase):
    """La capture est remplacée par une fausse : on vérifie ce qu'on en fait."""

    def setUp(self):
        from PIL import Image

        from tablette.ecrans_dcs import NOM_FICHIER, disposition_essai, generer

        self.Image = Image
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Config" / "MonitorSetup").mkdir(parents=True)
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), disposition_essai(2560, 1440), "test"),
            encoding="ascii")
        (self.saved / "Config" / "options.lua").write_text(
            '["height"] = 1440,\n["multiMonitorSetup"] = "tablette",\n'
            '["width"] = 2560,\n', encoding="utf-8")
        self.taille = (2560, 1440)
        self.absente = False
        self.captures = 0
        self.couleur = (40, 200, 60)      # le fond de l'écran exporté
        self.cockpit = (150, 150, 150)    # le liseré que DCS laisse autour
        self.vue = (90, 90, 90)           # le reste de la fenêtre
        self.instant = 0.0
        self.lancement = None             # DCS « lancé » : heure, ou None

    def tearDown(self):
        self.tmp.cleanup()

    def video(self):
        from PIL import ImageDraw

        from tablette.copie import decouper
        from tablette.ecrans_dcs import disposition_essai
        from tablette.video import Video

        def capturer(zones):
            self.captures += 1
            self.dernieres = set(zones)
            if self.absente:
                return None
            fenetre = self.Image.new("RGB", self.taille, self.vue)
            dessin = ImageDraw.Draw(fenetre)
            for x, y, l, h in disposition_essai(2560, 1440).values():
                dessin.rectangle((x, y, x + l - 1, y + h - 1), fill=self.couleur,
                                 outline=self.cockpit, width=4)
            return decouper(fenetre, zones)

        return Video(self.saved, capturer=capturer, lancement=lambda: self.lancement,
                     horloge=lambda: self.instant)

    def decoder(self, donnees):
        import io
        self.assertEqual(donnees[:3], b"\xff\xd8\xff")
        return self.Image.open(io.BytesIO(donnees)).convert("RGB")

    def test_ecran_decoupe_sans_le_liseré_du_cockpit(self):
        image = self.decoder(self.video().image("LEFT_MFCD"))
        self.assertEqual(image.size, (468, 468))          # 6 px rognés par bord
        for coin in ((0, 0), (467, 0), (0, 467), (467, 467)):
            r, v, b = image.getpixel(coin)
            self.assertLess(abs(v - 200) + abs(r - 40), 40, coin)

    def test_une_copie_sert_tous_les_ecrans_affiches(self):
        video = self.video()
        for viewport in ("LEFT_MFCD", "RIGHT_MFCD", "CENTER_MFCD"):
            video.image(viewport)              # la page démarre : chacun se présente
        self.instant += 0.1
        self.captures = 0
        for viewport in ("LEFT_MFCD", "RIGHT_MFCD", "CENTER_MFCD", "LEFT_MFCD"):
            video.image(viewport)
        self.assertEqual(self.captures, 1)

    def test_seuls_les_ecrans_affiches_sont_copies(self):
        video = self.video()
        video.image("CENTER_MFCD")             # l'AMPCD, affiché un moment…
        for _ in range(3):                     # …puis la page passe aux deux DDI
            self.instant += 0.6
            video.image("LEFT_MFCD")
            video.image("RIGHT_MFCD")
        self.assertEqual(self.dernieres, {"LEFT_MFCD", "RIGHT_MFCD"})

    def test_temoin_copie_seulement_pour_un_ecran_noir(self):
        video = self.video()
        video.image("LEFT_MFCD")
        self.assertEqual(self.captures, 1)
        self.couleur = self.cockpit = (0, 0, 0)
        self.instant += 0.1
        video.image("LEFT_MFCD")
        self.assertEqual(self.captures, 3)     # la copie, puis le témoin
        self.assertEqual(self.dernieres, {"TEMOIN"})

    def test_ecran_eteint_servi_mais_capture_aveugle_signalee(self):
        from tablette.video import PasDImage
        self.couleur = self.cockpit = (0, 0, 0)
        self.decoder(self.video().image("CENTER_MFCD"))
        self.vue = (0, 0, 0)
        with self.assertRaises(PasDImage) as e:
            self.video().image("CENTER_MFCD")
        self.assertIn("Plein écran", str(e.exception))

    def test_raisons_sans_image(self):
        from tablette.video import PasDImage
        self.absente = True
        with self.assertRaises(PasDImage) as e:
            self.video().image("LEFT_MFCD")
        self.assertIn("pas lancé", str(e.exception))
        self.absente = False
        # Configuration d'écrans qui ne correspond plus à la fenêtre.
        from tablette.ecrans_dcs import NOM_FICHIER, generer
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), {"RIGHT_MFCD": (0, 1440, 800, 800)}, "test"),
            encoding="ascii")
        with self.assertRaises(PasDImage) as e:
            self.video().image("RIGHT_MFCD")
        self.assertIn("sort de la fenêtre", str(e.exception))

    def test_configuration_reecrite_apres_le_lancement_de_dcs(self):
        """Vu en vrai : réécrite pendant que DCS tournait, la configuration ne
        disait plus où DCS dessinait, et l'iPad montrait n'importe quoi."""
        import os

        from tablette.ecrans_dcs import NOM_FICHIER
        from tablette.video import PasDImage
        fichier = self.saved / "Config" / "MonitorSetup" / NOM_FICHIER
        os.utime(fichier, (1_000_000, 1_000_000))
        self.lancement = 2_000_000.0                    # DCS lancé après : bon
        self.video().image("LEFT_MFCD")
        self.lancement = 500_000.0                      # DCS lancé avant : non
        with self.assertRaises(PasDImage) as e:
            self.video().image("LEFT_MFCD")
        self.assertIn("relance DCS", str(e.exception))

    def test_fenetre_plus_petite_que_la_resolution_reglee(self):
        """Vu en vrai : DCS réglé en 2560 × 2240 sur un écran de 1440 de haut
        garde une fenêtre de 2560 × 1440 ; le dire tel quel."""
        from tablette.video import PasDImage
        (self.saved / "Config" / "options.lua").write_text(
            '["height"] = 2240,\n["multiMonitorSetup"] = "tablette",\n'
            '["width"] = 2560,\n', encoding="utf-8")
        from tablette.ecrans_dcs import NOM_FICHIER, generer
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), {"LEFT_MFCD": (0, 1440, 800, 800)}, "test"),
            encoding="ascii")
        with self.assertRaises(PasDImage) as e:
            self.video().image("LEFT_MFCD")
        self.assertIn("réglé en 2560 × 2240 mais sa fenêtre ne fait que 2560 × 1440",
                      str(e.exception))


class TestKneeboardDCS(unittest.TestCase):
    """Écran virtuel à droite : DCS ouvre le kneeboard sur lui, on le capture."""

    def setUp(self):
        from PIL import Image

        from tablette.ecrans_dcs import NOM_FICHIER, disposition_second_ecran, generer

        self.Image = Image
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        (self.saved / "Config" / "MonitorSetup").mkdir(parents=True)
        self.zones = disposition_second_ecran(2560, 1440, 2560, 1440)
        (self.saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), self.zones, "test"), encoding="ascii")
        (self.saved / "Config" / "options.lua").write_text(
            '["height"] = 1440,\n["multiMonitorSetup"] = "tablette",\n'
            '["width"] = 5120,\n', encoding="utf-8")
        self.ouvert = True

    def tearDown(self):
        self.tmp.cleanup()

    def video(self):
        from PIL import ImageDraw

        from tablette.copie import decouper
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.video import Video

        def capturer(zones):
            fenetre = self.Image.new("RGB", (5120, 1440), (0, 0, 0))
            dessin = ImageDraw.Draw(fenetre)
            dessin.rectangle((0, 0, 2559, 1439), fill=(90, 90, 90))      # la vue
            for x, y, l, h in self.zones.values():
                dessin.rectangle((x, y, x + l - 1, y + h - 1), fill=(40, 200, 60))
            if self.ouvert:
                x, y, l, h = zone_kneeboard(5120, 1440)
                dessin.rectangle((x, y, x + l - 1, y + h - 1), fill=(250, 240, 150))
            return decouper(fenetre, zones)

        return Video(self.saved, capturer=capturer, lancement=lambda: None)

    def test_page_ouverte_capturee_entiere(self):
        page = self.video().kneeboard()
        self.assertEqual(page.size, (720, 1084))
        self.assertEqual(page.getpixel((360, 540)), (250, 240, 150))

    def test_kneeboard_ferme_dit_comment_l_ouvrir(self):
        from tablette.video import PasDImage
        self.ouvert = False
        with self.assertRaises(PasDImage) as e:
            self.video().image("KNEEBOARD")
        self.assertIn("RShift+K", str(e.exception))

    def test_ecran_debordant_ne_fait_pas_croire_le_kneeboard_ouvert(self):
        """Vu en vrai : avec l'ancienne disposition encore chargée par DCS, le
        DDI droit couvrait le haut de la zone ; le miroir montrait ce DDI."""
        from tablette.video import PasDImage
        self.ouvert = False
        self.zones["RIGHT_MFCD"] = (4266, 0, 853, 853)
        with self.assertRaises(PasDImage):
            self.video().kneeboard()

    def test_les_ddi_restent_intacts_kneeboard_ouvert(self):
        import io
        image = self.Image.open(io.BytesIO(self.video().image("RIGHT_MFCD")))
        r, v, b = image.convert("RGB").getpixel((image.width - 2, image.height - 2))
        self.assertLess(abs(v - 200) + abs(r - 40), 40)


class TestMiroir(unittest.TestCase):
    def test_miroir_seulement_si_le_kneeboard_quitte_l_ecran_principal(self):
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.miroir import sort_de_l_ecran_principal
        principal = (0, 0, 2560, 1440)
        self.assertTrue(sort_de_l_ecran_principal(zone_kneeboard(5120, 1440), principal))
        self.assertFalse(sort_de_l_ecran_principal(zone_kneeboard(2560, 1440), principal))
        # Écran virtuel dessous : à cheval sur les deux, le miroir aussi.
        self.assertTrue(sort_de_l_ecran_principal(zone_kneeboard(2560, 2880), principal))

    def test_temoin_dans_la_vue_principale_quel_que_soit_le_cote(self):
        from tablette.copie import zone_temoin
        for taille, principal in (((5120, 1440), (0, 0, 2560, 1440)),
                                  ((2560, 2880), (0, 0, 2560, 1440)),
                                  ((2560, 1440), (0, 0, 2560, 1440))):
            x, y, l, h = zone_temoin(taille)
            px, py, pl, ph = principal
            self.assertTrue(px <= x and x + l <= px + pl and py <= y and y + h <= py + ph, taille)

    def test_place_la_ou_dcs_l_aurait_mis_sur_un_ecran_unique(self):
        from tablette.ecrans_dcs import zone_kneeboard
        from tablette.miroir import place_miroir
        self.assertEqual(place_miroir((0, 0, 2560, 1440), (720, 1084)),
                         zone_kneeboard(2560, 1440))
        # Barre des tâches de 48 px en bas : le miroir se pose au-dessus.
        self.assertEqual(place_miroir((0, 0, 2560, 1392), (720, 1084)),
                         (1840, 308, 720, 1084))

    def test_kneeboard_rendu_au_pc_quand_la_tablette_se_tait(self):
        from tablette.miroir import AffichageKneeboard, Miroir
        maintenant = [100.0]
        affichage = AffichageKneeboard(horloge=lambda: maintenant[0])
        miroir = Miroir(video=None, saved_games=Path("."), affichage=affichage)
        self.assertTrue(miroir._sur_pc())
        affichage.choisir("tablette")
        self.assertFalse(miroir._sur_pc())
        maintenant[0] += 9
        self.assertEqual(affichage.effectif(), "tablette")
        maintenant[0] += 2                  # 11 s sans nouvelles de la tablette
        self.assertEqual(affichage.effectif(), "pc")
        affichage.choisir("ailleurs")       # ignoré
        self.assertEqual(affichage.effectif(), "pc")


class FauxLua:
    """Joue le rôle de DCS-Tablette-Export.lua sur des ports éphémères."""

    def __init__(self):
        self.ecoute = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.settimeout(2)
        self.port = self.ecoute.getsockname()[1]

    def recevoir(self) -> str:
        return self.ecoute.recvfrom(64)[0].decode("ascii")

    def annoncer(self, port_etat: int, nom: str) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(f"etat {nom}".encode(), ("127.0.0.1", port_etat))
        s.close()

    def fermer(self):
        self.ecoute.close()


class TestApiTablette(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        from tablette.dcs import PontDCS

        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.saved = Path(self.tmp.name)
        self.lua = FauxLua()
        self.pont = PontDCS(port_ordres=self.lua.port, port_etat=0)
        self.pont.demarrer()
        cfg = Config(saved_games=self.saved)
        self.dossier_dcs = None             # le DCS du poste n'entre pas dans les tests
        self.client = TestClient(create_app(cfg, self.pont,
                                            dossier_dcs=lambda: self.dossier_dcs))

    def tearDown(self):
        self.pont.arreter()
        self.lua.fermer()
        self.tmp.cleanup()

    def bouton(self, ecran, bouton, enfonce=True, **autres):
        return self.client.post("/api/bouton", json={"ecran": ecran, "bouton": bouton,
                                                     "enfonce": enfonce, **autres})

    def piloter(self, nom):
        """Fait annoncer `nom` par le faux script, et attend que le serveur suive."""
        self.lua.annoncer(self.pont.port_etat, nom)
        for _ in range(100):
            if self.client.get("/api/etat").json()["dcs"]["appareil"] == nom:
                return
            time.sleep(0.02)
        self.fail(f"{nom} jamais annoncé")

    def silence(self):
        self.lua.ecoute.settimeout(0.3)
        with self.assertRaises(socket.timeout):
            self.lua.recevoir()

    def test_appareil_choisi_a_la_main_et_garde_fou(self):
        """Le menu de la tablette (cookie) prépare la page avant la mission ;
        mais rien ne part vers un DCS qui pilote autre chose : l'OSB 1 du MFD
        droit du F-16 y serait l'A/P de l'UFC du Hornet."""
        self.assertIn("ah64d", [p["id"] for p in self.client.get("/api/profils").json()])
        self.client.cookies.set("tablette_appareil", "ah64d")
        self.assertEqual(self.client.get("/api/profil").json()["id"], "ah64d")
        e = self.client.get("/api/etat").json()
        self.assertEqual((e["profil"], e["choisi"], e["ailleurs"]), ("ah64d", True, None))

        self.piloter("FA-18C_hornet")
        e = self.client.get("/api/etat").json()
        self.assertEqual((e["profil"], e["ailleurs"]), ("ah64d", "F/A-18C Hornet"))
        r = self.bouton("mpd_gauche", "T1")
        self.assertEqual(r.status_code, 409)
        self.assertIn("boutons coupés", r.json()["detail"])
        self.silence()

        self.piloter("AH-64D_BLK_II")
        self.assertEqual(self.bouton("mpd_gauche", "T1").json(), {"envoye": True})
        self.assertEqual(self.lua.recevoir(), "42 3001 1")

        # Hornet choisi, F-16 piloté : l'UFC non plus ne part pas.
        self.client.cookies.set("tablette_appareil", "fa18c")
        self.piloter("F-16C_50")
        self.assertEqual(self.client.post("/api/ufc", json={"touche": "AP", "enfonce": True})
                         .status_code, 409)
        self.silence()
        # Auto : la page suit de nouveau DCS.
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/profil").json()["id"], "f16c")

    def test_coins_des_ecrans_selon_l_appareil(self):
        """Arrondis mesurés sur le Hornet seulement ; l'Apache est quasi carré."""
        hornet = appareils.profil_par_id("fa18c").description()["ecrans"]
        apache = appareils.profil_par_id("ah64d").description()["ecrans"]
        self.assertEqual({e["arrondi"] for e in hornet}, {0.17})
        self.assertTrue(all(e["arrondi"] <= 0.02 for e in apache))

    def test_page_installable_sur_l_ecran_d_accueil(self):
        """Android lit le manifeste, iOS l'icône 180 : nom, icône, plein écran."""
        page = self.client.get("/").text
        self.assertIn('href="/manifest.webmanifest"', page)
        self.assertIn('href="/icone-180.png"', page)
        manifeste = self.client.get("/manifest.webmanifest").json()
        self.assertEqual(manifeste["display"], "fullscreen")
        for icone in manifeste["icons"] + [{"src": "/icone-180.png"}]:
            r = self.client.get(icone["src"])
            self.assertEqual(r.status_code, 200, icone["src"])
            self.assertTrue(r.content.startswith(b"\x89PNG"), icone["src"])
        self.assertEqual(self.client.get("/icone-64.png").status_code, 404)

    def test_appui_puis_relachement_arrivent_au_script(self):
        self.assertEqual(self.bouton("ddi_gauche", "18").json(), {"envoye": True})
        self.assertEqual(self.lua.recevoir(), "35 3028 1")
        self.bouton("ddi_gauche", "18", enfonce=False)
        self.assertEqual(self.lua.recevoir(), "35 3028 0")

    def test_chaque_appui_est_ecrit_dans_le_journal(self):
        with self.assertLogs("tablette", level="INFO") as journal:
            self.bouton("ddi_droit", "7")
        self.lua.recevoir()
        self.assertEqual(len(journal.output), 1)
        # Sans annonce du script, l'ordre part mais personne ne l'écoute.
        self.assertIn("DDI droit 7 enfoncé — DCS ne répond pas", journal.output[0])

    def test_ampcd_et_ddi_droit(self):
        self.bouton("ampcd", "1")
        self.assertEqual(self.lua.recevoir(), "37 3011 1")
        self.bouton("ddi_droit", "20")
        self.assertEqual(self.lua.recevoir(), "36 3030 1")

    def test_ordres_invalides_refuses_sans_rien_envoyer(self):
        self.assertEqual(self.bouton("hud", "1").status_code, 404)
        for b in ("0", "21", "x", None):
            self.assertEqual(self.bouton("ddi_gauche", b).status_code, 422, b)
        self.silence()

    def test_le_profil_suit_l_appareil_et_le_siege(self):
        self.assertEqual(self.client.get("/api/profil").json()["id"], "fa18c")
        self.piloter("AH-64D_BLK_II")
        profil = self.client.get("/api/profil").json()
        self.assertEqual((profil["id"], profil["sieges"]), ("ah64d", ["pilote", "cpg"]))
        self.assertEqual([e["id"] for e in profil["ecrans"]], ["mpd_gauche", "mpd_droit", "tedac"])
        self.bouton("mpd_gauche", "T1", siege="cpg")
        self.assertEqual(self.lua.recevoir(), "44 3001 1")
        self.bouton("mpd_droit", "M", siege="pilote")       # « M » est B1
        self.bouton("mpd_droit", "B1", siege="pilote")
        self.assertEqual(self.lua.recevoir(), "43 3018 1")
        # Les écrans du Hornet n'existent plus : rien ne part.
        self.assertEqual(self.bouton("ddi_gauche", "18").status_code, 404)
        self.assertEqual(self.client.get("/api/planche").status_code, 404)
        self.client.post("/api/kneeboard/dcs/page", json={"sens": 1})
        self.assertEqual(self.lua.recevoir(), "84 3001 1")
        # Le dernier profil reste quand DCS se tait.
        self.lua.annoncer(self.pont.port_etat, "-")
        time.sleep(0.1)
        self.assertEqual(self.client.get("/api/profil").json()["id"], "ah64d")

    def test_appareil_sans_page_de_kneeboard_sure(self):
        self.piloter("F-16C_50")
        r = self.client.post("/api/kneeboard/dcs/page", json={"sens": 1})
        self.assertEqual(r.status_code, 409)
        self.silence()
        self.piloter("Christen Eagle II")
        profil = self.client.get("/api/profil").json()
        self.assertEqual((profil["id"], profil["ecrans"]), ("generique", []))

    def test_planche_du_hornet(self):
        self.lua.annoncer(self.pont.port_etat, "FA-18C_hornet")
        envoi = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        envoi.sendto(("ind 6\n" + TestPlanche.TEXTE_UFC).encode(),
                     ("127.0.0.1", self.pont.port_etat))
        envoi.sendto(b"arg 217=0.586 13=1.0", ("127.0.0.1", self.pont.port_etat))
        envoi.close()
        for _ in range(100):
            d = self.client.get("/api/planche").json()
            if d["ufc"] and d["instruments"]:
                break
            time.sleep(0.02)
        self.assertEqual(d["ufc"]["bloc"][2], "  127.500")
        self.assertEqual(d["instruments"]["badin"]["valeur"], 200.0)
        self.assertTrue(d["voyants"]["MASTER CAUTION"])
        self.assertIsNone(d["ifei"])                      # rien reçu : rien inventé

    def test_touches_et_molettes_de_l_ufc(self):
        self.client.post("/api/ufc", json={"touche": "ENT", "enfonce": True})
        self.assertEqual(self.lua.recevoir(), "25 3029 1")
        self.client.post("/api/ufc", json={"touche": "COMM1", "sens": -1})
        self.assertEqual(self.lua.recevoir(), "25 3033 -0.2")
        self.assertEqual(self.client.post("/api/ufc", json={"touche": "HUD"}).status_code, 404)
        self.assertEqual(self.client.post("/api/ufc", json={"touche": "COMM2", "sens": 3}
                                          ).status_code, 422)
        self.silence()

    def test_etat_suit_les_annonces_du_script(self):
        self.assertEqual(self.client.get("/api/etat").json()["dcs"],
                         {"connecte": False, "appareil": None})
        self.lua.annoncer(self.pont.port_etat, "FA-18C_hornet")
        for _ in range(50):
            dcs = self.client.get("/api/etat").json()["dcs"]
            if dcs["connecte"]:
                break
            time.sleep(0.02)
        self.assertEqual(dcs, {"connecte": True, "appareil": "FA-18C_hornet"})
        self.lua.annoncer(self.pont.port_etat, "-")
        for _ in range(50):
            dcs = self.client.get("/api/etat").json()["dcs"]
            if dcs["appareil"] is None:
                break
            time.sleep(0.02)
        self.assertEqual(dcs, {"connecte": True, "appareil": None})

    def test_ecrans_decrits_pour_la_page(self):
        profil = self.client.get("/api/profil").json()
        self.assertEqual([e["id"] for e in profil["ecrans"]], ["ddi_gauche", "ddi_droit", "ampcd"])
        self.assertEqual(len(profil["ecrans"][0]["boutons"]), 20)
        self.assertEqual(profil["panneaux"], ["ufc", "ifei", "secours"])

    def test_kneeboard_dossier_et_mission(self):
        (self.saved / "Kneeboard" / "FA-18C_hornet").mkdir(parents=True)
        (self.saved / "Kneeboard" / "commune.png").write_bytes(PNG)
        (self.saved / "Kneeboard" / "FA-18C_hornet" / "hornet.png").write_bytes(PNG)
        (self.saved / "Kneeboard" / "notes.txt").write_text("pas une page")
        (self.saved / "Missions").mkdir()
        with zipfile.ZipFile(self.saved / "Missions" / "Vol test.miz", "w") as z:
            z.writestr("mission", "x")
            z.writestr("KNEEBOARD/IMAGES/briefing.png", PNG)
        with zipfile.ZipFile(self.saved / "Missions" / "Sans pages.miz", "w") as z:
            z.writestr("mission", "x")

        carnets = self.client.get("/api/kneeboard").json()
        self.assertEqual([(c["id"], c["pages"]) for c in carnets],
                         [("avion", 2), ("miz:Vol test.miz", 1)])
        for c in carnets:
            r = self.client.get(c["url"] + "/0")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers["content-type"], "image/png")
            self.assertEqual(r.content, PNG)
        self.assertEqual(self.client.get(carnets[0]["url"] + "/2").status_code, 404)
        self.assertEqual(self.client.get("/api/kneeboard/inconnu/0").status_code, 404)

    def test_mission_en_cours_retrouvee_dans_le_journal_de_dcs(self):
        """Vu en vrai : une mission jouée depuis une copie temporaire, hors du
        dossier Missions ; seul dcs.log dit laquelle."""
        temporaire = self.saved / "Temp" / "tempMission.miz"
        temporaire.parent.mkdir()
        with zipfile.ZipFile(temporaire, "w") as z:
            z.writestr("mission", "x")
            z.writestr("KNEEBOARD/FA-18C_hornet/IMAGES/carte.png", PNG)
        (self.saved / "Logs").mkdir()
        (self.saved / "Logs" / "dcs.log").write_text(
            "2026-10-25 16:28:22.965 INFO    Dispatcher (Main): loadMission "
            f"{temporaire}\r\n"
            "2026-10-25 16:28:37.552 INFO    Dispatcher (Main): loadMission Done: "
            "Control passed to the player\r\n", encoding="utf-8")
        carnets = self.client.get("/api/kneeboard").json()
        self.assertEqual((carnets[0]["id"], carnets[0]["titre"], carnets[0]["pages"]),
                         ("avion", "Kneeboard de l'avion", 1))
        self.assertEqual(self.client.get(carnets[0]["url"] + "/0").content, PNG)

    def test_kneeboard_de_l_avion_en_multijoueur(self):
        """Vu dans dcs.log : en multijoueur, DCS charge la mission du serveur
        depuis l'enregistrement de la partie (.trk). Kneeboard de l'avion :
        mission, puis module, puis pages perso ; cartes à part."""
        import io

        from PIL import Image

        from tablette.kneeboard import lister_carnets
        trk = self.saved / "Tracks" / "Multiplayer" / "Op-20261026-211500.trk"
        trk.parent.mkdir(parents=True)
        with zipfile.ZipFile(trk, "w") as z:
            z.writestr("mission", 'mission = {\n\t["theatre"] = "Caucasus",\n}\n')
            z.writestr("KNEEBOARD/IMAGES/freq.png", PNG)
            z.writestr("KNEEBOARD/FA-18C_hornet/IMAGES/carte.png", PNG)
            z.writestr("KNEEBOARD/F-16C_50/IMAGES/viper.png", PNG)       # pas pour nous
        (self.saved / "Logs").mkdir()
        (self.saved / "Logs" / "dcs.log").write_text(
            f"2026-10-26 21:15:00.000 INFO    Dispatcher (Main): loadMission {trk}\r\n",
            encoding="utf-8")
        (self.saved / "Kneeboard" / "FA-18C_hornet").mkdir(parents=True)
        (self.saved / "Kneeboard" / "FA-18C_hornet" / "perso.png").write_bytes(PNG)
        (self.saved / "Kneeboard" / "commune.png").write_bytes(PNG)

        # Un dossier DCS : le module (dossier « FA-18C », appareil
        # « FA-18C_hornet ») et la carte (planches, dont une en BMP).
        dcs = self.saved / "DCSWorld"
        module = dcs / "Mods" / "aircraft" / "FA-18C"
        (module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages").mkdir(parents=True)
        (module / "entry.lua").write_text(
            "make_flyable('FA-18C_hornet', current_mod_path..'/Cockpit/Scripts/', nil)")
        (module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages" / "1.png").write_bytes(PNG)
        (module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages" / "1.lua").write_text("--")
        terrain = dcs / "Mods" / "terrains" / "Caucasus"
        (terrain / "Kneeboard").mkdir(parents=True)
        (terrain / "entry.lua").write_text('local self_ID = "Caucasus";\n')   # tel quel
        (terrain / "Kneeboard" / "00_map.png").write_bytes(PNG)
        tampon = io.BytesIO()
        Image.new("RGB", (4, 6), "white").save(tampon, "BMP")
        (terrain / "Kneeboard" / "01_kobuleti.bmp").write_bytes(tampon.getvalue())

        carnets = lister_carnets(self.saved, "FA-18C_hornet", dcs)
        noms = {c.id: [p.name if isinstance(p, Path) else p[1] for p in c.pages] for c in carnets}
        self.assertEqual(noms["avion"], [
            "KNEEBOARD/FA-18C_hornet/IMAGES/carte.png", "KNEEBOARD/IMAGES/freq.png",
            "1.png", "perso.png", "commune.png"])
        self.assertEqual(noms["carte:Caucasus"], ["00_map.png", "01_kobuleti.bmp"])
        self.assertEqual([c.titre for c in carnets][:2], ["Kneeboard de l'avion", "Cartes : Caucasus"])

        # Par l'API, DCS une fois connu : la planche BMP arrive en PNG.
        self.dossier_dcs = dcs
        r = self.client.get("/api/kneeboard/carte%3ACaucasus/1")
        self.assertEqual((r.status_code, r.headers["content-type"]), (200, "image/png"))
        self.assertEqual(Image.open(io.BytesIO(r.content)).size, (4, 6))
        self.dossier_dcs = None             # DCS fermé : le dernier dossier connu sert
        self.assertEqual(self.client.get("/api/kneeboard").json()[1]["id"], "carte:Caucasus")

    def test_kneeboard_de_dcs_sur_pc_ou_tablette(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config

        class FausseVideo:
            def kneeboard_ouvert(self):
                return True

        client = TestClient(create_app(Config(saved_games=self.saved), self.pont,
                                       FausseVideo(), dossier_dcs=lambda: None))
        self.assertEqual(client.get("/api/etat").json()["kneeboard"],
                         {"sur": "pc", "ouvert": None})
        # DCS muet : la tablette prend le kneeboard, sans savoir s'il est ouvert.
        self.assertEqual(client.get("/api/etat?kneeboard=tablette").json()["kneeboard"],
                         {"sur": "tablette", "ouvert": None})
        self.lua.annoncer(self.pont.port_etat, "FA-18C_hornet")
        for _ in range(100):
            if client.get("/api/etat").json()["dcs"]["connecte"]:
                break
            time.sleep(0.02)
        self.assertEqual(client.get("/api/etat?kneeboard=tablette").json()["kneeboard"],
                         {"sur": "tablette", "ouvert": True})
        self.assertEqual(client.get("/api/etat?kneeboard=pc").json()["kneeboard"],
                         {"sur": "pc", "ouvert": None})

    def test_kneeboard_de_dcs_affiche_depuis_la_tablette(self):
        """Le coup d'œil (K) : +1 l'affiche, -1 le cache ; rien d'autre."""
        self.client.post("/api/kneeboard/dcs/affichage", json={"ouvert": True})
        self.assertEqual(self.lua.recevoir(), "kneeboard 1")
        self.client.post("/api/kneeboard/dcs/affichage", json={"ouvert": False})
        self.assertEqual(self.lua.recevoir(), "kneeboard -1")
        for valeur in (1, "true", None):
            r = self.client.post("/api/kneeboard/dcs/affichage", json={"ouvert": valeur})
            self.assertEqual(r.status_code, 422, valeur)
        self.silence()

    def test_version_dans_l_etat(self):
        """La page se recharge quand le serveur change de version."""
        from tablette import VERSION
        self.assertEqual(self.client.get("/api/etat").json()["version"], VERSION)

    def test_pages_du_kneeboard_de_dcs(self):
        self.client.post("/api/kneeboard/dcs/page", json={"sens": 1})
        self.assertEqual(self.lua.recevoir(), "68 3001 1")
        self.client.post("/api/kneeboard/dcs/page", json={"sens": -1})
        self.assertEqual(self.lua.recevoir(), "68 3002 1")
        for sens in (0, 2, "1", None):
            r = self.client.post("/api/kneeboard/dcs/page", json={"sens": sens})
            self.assertEqual(r.status_code, 422, sens)

    def test_image_servie_ou_raison_donnee(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        from tablette.video import PasDImage

        class FausseVideo:
            def image(self, viewport, luminosite=0):
                if viewport == "CENTER_MFCD":
                    raise PasDImage("CENTER_MFCD non exporté")
                return b"\xff\xd8\xff" + viewport.encode()

        client = TestClient(create_app(Config(saved_games=self.saved), self.pont,
                                       FausseVideo()))
        r = client.get("/api/video/ddi_droit")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/jpeg")
        self.assertEqual(r.content, b"\xff\xd8\xffRIGHT_MFCD")
        r = client.get("/api/video/ampcd")
        self.assertEqual((r.status_code, r.json()["detail"]), (503, "CENTER_MFCD non exporté"))
        self.assertEqual(client.get("/api/video/kneeboard").content, b"\xff\xd8\xffKNEEBOARD")
        self.assertEqual(client.get("/api/video/hud").status_code, 404)

    def test_page_servie(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("DCS Tablette", r.text)


class TestMiseAJour(unittest.TestCase):
    """Mise à jour depuis GitHub, simulée : rien n'est téléchargé ni remplacé."""

    def reponse(self, donnees: bytes):
        import contextlib
        return contextlib.nullcontext(io.BytesIO(donnees))

    def publication(self, version="9.0.0", digest=True, corps=None):
        import json
        zip_ = {"name": f"DCS-Tablette-{version}.zip", "size": 24_000_000,
                "browser_download_url": f"https://exemple/{version}.zip"}
        if digest:
            zip_["digest"] = "sha256:" + "a" * 64
        corps = corps if corps is not None else (
            "## Nouveau\n\n- **Une nouveauté.** Expliquée.\n- Une autre.\n\n## Mettre à jour\n\n"
            f"SHA-256 de `DCS-Tablette-{version}.zip` :\n```\n{'b' * 64}\n```\n")
        return json.dumps({"tag_name": f"v{version}", "assets": [zip_], "body": corps}).encode()

    def test_derniere_version_et_son_empreinte(self):
        from tablette.mise_a_jour import derniere_version
        lire = lambda donnees: (lambda requete, timeout: self.reponse(donnees))  # noqa: E731
        publiee = derniere_version(lire(self.publication()))
        self.assertEqual((publiee["version"], publiee["empreinte"]), ("9.0.0", "a" * 64))
        # GitHub sans empreinte : celle des notes de version.
        self.assertEqual(derniere_version(lire(self.publication(digest=False)))["empreinte"],
                         "b" * 64)
        # Ni l'une ni l'autre : on ne propose rien qu'on ne puisse vérifier.
        self.assertIsNone(derniere_version(lire(self.publication(digest=False, corps=""))))

        def hors_ligne(requete, timeout):
            raise OSError("pas de réseau")
        self.assertIsNone(derniere_version(hors_ligne))

    def test_comparaison_des_versions(self):
        from tablette.mise_a_jour import numero, plus_recente
        self.assertGreater(numero("v1.10.0"), numero("1.9.9"))       # pas l'ordre du texte
        self.assertTrue(plus_recente({"version": "1.5.0"}, "1.4.0"))
        self.assertFalse(plus_recente({"version": "1.4.0"}, "1.4.0"))
        self.assertFalse(plus_recente(None, "1.4.0"))

    def test_nouveautes_des_notes(self):
        import json

        from tablette.mise_a_jour import nouveautes
        corps = json.loads(self.publication())["body"]
        self.assertEqual(nouveautes(corps), ["Une nouveauté. Expliquée.", "Une autre."])

    def zip_publie(self, avec_exe=True):
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("DCS-Tablette/LISEZ-MOI.txt", "lisez")
            if avec_exe:
                z.writestr("DCS-Tablette/DCS-Tablette.exe", "MZ")
        return tampon.getvalue()

    def test_telechargement_verifie_avant_tout(self):
        import hashlib

        from tablette.mise_a_jour import telecharger
        donnees = self.zip_publie()
        ouvrir = lambda url, timeout: self.reponse(donnees)        # noqa: E731
        with tempfile.TemporaryDirectory() as dossier:
            publiee = {"version": "9.0.0", "url": "u",
                       "empreinte": hashlib.sha256(donnees).hexdigest()}
            source = telecharger(publiee, Path(dossier), ouvrir)
            self.assertTrue((source / "DCS-Tablette.exe").exists())
        with tempfile.TemporaryDirectory() as dossier:
            with self.assertRaises(OSError):                       # empreinte différente
                telecharger(dict(publiee, empreinte="0" * 64), Path(dossier), ouvrir)
            self.assertFalse((Path(dossier) / "extrait").exists())  # rien d'extrait
        sans_exe = self.zip_publie(avec_exe=False)
        with tempfile.TemporaryDirectory() as dossier, self.assertRaises(OSError):
            telecharger(dict(publiee, empreinte=hashlib.sha256(sans_exe).hexdigest()),
                        Path(dossier), lambda url, timeout: self.reponse(sans_exe))

    def proposer(self, reponse, publiee):
        from unittest import mock

        from tablette import mise_a_jour
        lignes, lances = [], []
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(mise_a_jour.tempfile, "mkdtemp", lambda prefix: temp.name), \
                mock.patch.object(mise_a_jour, "telecharger",
                                  lambda p, d: d / "extrait" / "DCS-Tablette"), \
                mock.patch.object(mise_a_jour, "lancer_remplacement",
                                  lambda *a: lances.append(a)):
            relance = mise_a_jour.proposer(lignes.append, lambda q: reponse, publiee)
        return relance, lances, "\n".join(lignes)

    def test_proposee_et_lancee_seulement_avec_accord(self):
        from tablette.mise_a_jour import derniere_version
        publiee = derniere_version(lambda r, timeout: self.reponse(self.publication()))
        relance, lances, texte = self.proposer("", publiee)
        self.assertTrue(relance)
        self.assertEqual(len(lances), 1)
        self.assertIn("9.0.0", texte)
        self.assertIn("Une nouveauté", texte)
        relance, lances, texte = self.proposer("n", publiee)
        self.assertEqual((relance, lances), (False, []))
        self.assertIn("reproposera", texte)
        relance, lances, _ = self.proposer(None, publiee)          # pas de console
        self.assertEqual((relance, lances), (False, []))
        a_jour = dict(publiee, version="0.1")
        self.assertEqual(self.proposer("", a_jour)[:2], (False, []))

    def test_le_script_de_remplacement_passe_tout_par_l_environnement(self):
        from tablette.mise_a_jour import REMPLACER
        self.assertTrue(REMPLACER.isascii())          # lu par cmd tel quel
        for variable in ("%DT_PID%", "%DT_SOURCE%", "%DT_CIBLE%", "%DT_ZIP%"):
            self.assertIn(variable, REMPLACER)
        self.assertIn("Robocopy.exe", REMPLACER)
        self.assertIn("if errorlevel 8", REMPLACER)   # robocopy : 8 et plus = échec
        self.assertNotIn("(\n", REMPLACER)             # aucun bloc qu'un « ) » refermerait

    @unittest.skipUnless(sys.platform == "win32", "cmd et robocopy")
    def test_le_script_de_remplacement_avec_un_chemin_retors(self):
        """Exécuté pour de vrai par cmd : chemin avec espaces, ( ), & et
        accents, comme « DCS-Tablette (1) » d'un zip téléchargé deux fois.
        La relance de l'exe est remplacée par une trace."""
        import subprocess

        from tablette.mise_a_jour import REMPLACER, commande, environnement_remplacement
        with tempfile.TemporaryDirectory() as racine:
            racine = Path(racine) / "Pilote & Co (1) – été"
            temp = racine / "temp"
            source, cible = temp / "extrait" / "DCS-Tablette", racine / "DCS-Tablette (1)"
            (source / "_internal").mkdir(parents=True)
            (source / "DCS-Tablette.exe").write_text("nouveau")
            (source / "_internal" / "lib.dll").write_text("nouvelle")
            cible.mkdir()
            (cible / "DCS-Tablette.exe").write_text("ancien")
            (cible / "garde.txt").write_text("a moi")
            script = racine / "remplacer.bat"
            texte = REMPLACER.replace('start "" "%DT_CIBLE%\\DCS-Tablette.exe"',
                                      'echo relance>"%DT_CIBLE%\\relance.txt"')
            self.assertNotEqual(texte, REMPLACER)
            script.write_text(texte.replace("\n", "\r\n"), encoding="ascii")
            env = environnement_remplacement(source, cible, temp, temp / "x.zip")
            env["DT_PID"] = "999999"                   # déjà fermé
            sortie = subprocess.run(commande(script), env=env, capture_output=True, timeout=60)
            self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
            self.assertEqual((cible / "DCS-Tablette.exe").read_text(), "nouveau")
            self.assertEqual((cible / "_internal" / "lib.dll").read_text(), "nouvelle")
            self.assertEqual((cible / "garde.txt").read_text(), "a moi")
            self.assertTrue((cible / "relance.txt").exists())
            self.assertFalse(temp.exists())            # ménage fait

    def test_derniere_version_ne_leve_jamais(self):
        import http.client

        from tablette.mise_a_jour import derniere_version
        for panne in (http.client.IncompleteRead(b""), http.client.BadStatusLine("x"),
                      ValueError("json"), RuntimeError("?")):
            def ouvrir(requete, timeout, panne=panne):
                raise panne
            self.assertIsNone(derniere_version(ouvrir))
        self.assertIsNone(derniere_version(lambda r, timeout: self.reponse(b"[1, 2]")))
        self.assertIsNone(derniere_version(lambda r, timeout: self.reponse(b'{"tag_name": 5}')))

    def clavier(self, touches):
        """Un faux msvcrt qui rend `touches` une à une, et une console."""
        import types
        from unittest import mock
        touches = list(touches)
        faux = types.SimpleNamespace(kbhit=lambda: bool(touches),
                                     getwche=lambda: touches.pop(0))
        console = mock.Mock()
        console.isatty.return_value = True
        return mock.patch.dict(sys.modules, {"msvcrt": faux}), mock.patch.object(sys, "stdin", console)

    def test_question_qui_n_attend_pas_indefiniment(self):
        """Relancé en vol (retour du 30/10 : DCS ouvert, rien n'était proposé),
        la question attend un moment puis DCS Tablette démarre quand même."""
        import contextlib

        from tablette.mise_a_jour import demander_un_temps
        modules, stdin = self.clavier("o\r")
        with modules, stdin, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(demander_un_temps("? ", 2), "o")
        modules, stdin = self.clavier("")
        sortie = io.StringIO()
        debut = time.monotonic()
        with modules, stdin, contextlib.redirect_stdout(sortie):
            self.assertIsNone(demander_un_temps("? ", 0.3))
        self.assertLess(time.monotonic() - debut, 2)
        self.assertIn("sans mettre à jour", sortie.getvalue())

    def test_derniere_version_bornee_dans_le_temps(self):
        from unittest import mock

        from tablette import mise_a_jour

        def lent(requete, timeout):
            time.sleep(5)
            return self.reponse(self.publication())
        debut = time.monotonic()
        with mock.patch.object(mise_a_jour, "DELAI_S", 0.2):
            self.assertIsNone(mise_a_jour.derniere_version(lent))
        self.assertLess(time.monotonic() - debut, 2)

    def test_point_version_du_diagnostic(self):
        from tablette.diagnostic import Diagnostic
        from tablette import VERSION
        reglages = dict(ouvert=lambda: False, ecrans=lambda: [], virtuel=lambda *a: ("ok", "", []),
                        lancement=lambda: None, reseaux=lambda: [], choix=lambda: {})
        with tempfile.TemporaryDirectory() as dossier:
            points = {p.titre: p for p in Diagnostic(
                Path(dossier), publiee={"version": "99.0.0"}, **reglages).verifier()}
            self.assertIn("99.0.0 disponible", points["Version"].detail)
            points = {p.titre: p for p in Diagnostic(
                Path(dossier), publiee={"version": VERSION}, **reglages).verifier()}
            self.assertEqual(points["Version"].detail, f"{VERSION}, à jour")


class TestReseauLocal(unittest.TestCase):
    """Le serveur écoute tout le réseau local : un site piégé ne doit pas
    pouvoir appuyer sur les boutons ni déplacer les écrans."""

    def test_seuls_l_adresse_ip_et_le_nom_du_pc_passent(self):
        from tablette.app import hote_permis
        for hote in ("192.168.1.7:8320", "127.0.0.1:8320", "[fe80::1]:8320", "localhost:8320",
                     f"{socket.gethostname()}:8320", "192.168.1.7"):
            self.assertTrue(hote_permis(hote), hote)
        for hote in ("piege.example:8320", "piege.example", "", "192.168.1.7.nip.io:8320"):
            self.assertFalse(hote_permis(hote), hote)

    def test_un_nom_inconnu_est_refuse_par_le_serveur(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        app = create_app(Config(saved_games=Path(".")), FauxPont(), dossier_dcs=lambda: None,
                         controle_hote=True)
        self.assertEqual(TestClient(app, base_url="http://192.168.1.7:8320")
                         .get("/api/etat").status_code, 200)
        self.assertEqual(TestClient(app, base_url="http://piege.example:8320")
                         .get("/api/etat").status_code, 400)


class TestDesinstallation(unittest.TestCase):
    def test_attend_que_le_serveur_soit_ferme(self):
        import contextlib
        from unittest import mock

        from tablette import installation
        ouverts, questions = [1, 1, 0], []
        with tempfile.TemporaryDirectory() as dossier, \
                mock.patch.object(installation, "dossier_bureau", lambda: Path(dossier)), \
                mock.patch.object(installation, "fichier_choix",
                                  lambda: Path(dossier) / "installation.json"), \
                contextlib.redirect_stdout(io.StringIO()):
            installation.desinstaller(Path(dossier), demander=lambda q: questions.append(q) or "",
                                      autres=lambda: ouverts.pop(0))
        self.assertEqual(ouverts, [])
        self.assertEqual(len(questions), 2)
        self.assertIn("encore ouvert", questions[0])


LUA_DCS = Path("C:/Program Files (x86)/Steam/steamapps/common/DCSWorld/bin/lua.dll")


def executer_lua(prelude: str, script: Path, apres: str) -> str:
    """Exécute `script` dans le moteur Lua de DCS (son lua.dll), après
    `prelude` (un faux DCS) ; rend la valeur de RESULTAT laissée par `apres`.
    Le script de la tablette tourne pour de vrai, rien de DCS n'est appelé."""
    import ctypes
    dll = ctypes.CDLL(str(LUA_DCS))
    dll.luaL_newstate.restype = ctypes.c_void_p
    for f in ("luaL_openlibs", "lua_close"):
        getattr(dll, f).argtypes = [ctypes.c_void_p]
    dll.luaL_loadbuffer.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t,
                                    ctypes.c_char_p]
    dll.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    dll.lua_tolstring.restype = ctypes.c_char_p
    dll.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    dll.lua_getfield.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
    etat = dll.luaL_newstate()
    dll.luaL_openlibs(etat)
    try:
        for code, nom in ((prelude.encode(), b"=faux_dcs"), (script.read_bytes(), b"=script"),
                          (apres.encode(), b"=essai")):
            if dll.luaL_loadbuffer(etat, code, len(code), nom) or dll.lua_pcall(etat, 0, 0, 0):
                raise AssertionError(dll.lua_tolstring(etat, -1, None).decode(errors="replace"))
        dll.lua_getfield(etat, -10002, b"RESULTAT")          # LUA_GLOBALSINDEX (Lua 5.1)
        return (dll.lua_tolstring(etat, -1, None) or b"").decode()
    finally:
        dll.lua_close(etat)


FAUX_DCS = r'''
ENVOYES = {}
HORLOGE = 0
log = { INFO = 1, ERROR = 2, write = function() end }
package.preload["lfs"] = function() return { writedir = function() return "Z:/rien/" end,
                                             currentdir = function() return "Z:/rien" end } end
package.preload["socket"] = function()
  return { gettime = function() return HORLOGE end, udp = function()
    return { settimeout = function() end, setsockname = function() return 1 end,
             receive = function() return nil end, close = function() end,
             sendto = function(_, m) ENVOYES[#ENVOYES + 1] = m end } end }
end
EXPORT_PERMIS = true
function LoIsOwnshipExportAllowed() return EXPORT_PERMIS end
function LoGetSelfData() return { Name = "Christen Eagle II" } end
function LoGetIndicatedAirSpeed() return 100 end
function LoGetAltitudeAboveSeaLevel() return 1500 end
function LoGetVerticalVelocity() return -5 end
function LoGetADIPitchBankYaw() return 0.1, -0.2, 1.0 end
function LoGetMagneticYaw() return 1.5 end
function LoGetAccelerationUnits() return { x = 0, y = 1.5, z = 0 } end
function LoGetEngineInfo() return { RPM = { left = 75, right = 0 }, fuel_internal = 300 } end
function LoGetMechInfo() return { gear = { value = 1 }, flaps = { value = 0.5 } } end
'''


class TestInstrumentsDeVol(unittest.TestCase):
    """Les instruments de base, pour tout appareil (instruments.py)."""

    VOL = {"vi": 100.0, "alt": 1500.0, "vz": -5.0, "tang": 0.1, "roul": -0.2, "cap": 1.5,
           "g": 1.5, "rpm1": 75.0, "carb": 300.0, "train": 1.0, "volets": 0.5, "taux": 3.0}

    def test_unites_du_cockpit(self):
        from tablette.instruments import OTAN, WARBIRD_METRIQUE, WARBIRD_US, lecture
        self.assertEqual(lecture(self.VOL, OTAN)["badin"]["texte"], "194")            # kt
        self.assertEqual(lecture(self.VOL, WARBIRD_US)["badin"]["texte"], "224")      # mph
        self.assertEqual(lecture(self.VOL, WARBIRD_METRIQUE)["badin"]["texte"], "360")  # km/h
        self.assertEqual(lecture(self.VOL, OTAN)["altimetre"]["texte"], "4\u202f921")  # ft
        self.assertEqual(lecture(self.VOL, WARBIRD_METRIQUE)["altimetre"]["texte"], "1\u202f500")
        self.assertEqual(lecture(self.VOL, OTAN)["vario"]["texte"], "-980")          # ft/min
        self.assertEqual(lecture(self.VOL, WARBIRD_METRIQUE)["vario"]["texte"], "-5.0")
        bandeau = {b["titre"]: b["texte"] for b in lecture(self.VOL, OTAN)["bandeau"]}
        self.assertEqual(bandeau["CARBURANT"], "661 lb")
        self.assertEqual(bandeau["TRAIN"], "SORTI")
        self.assertIsNone(lecture(None, OTAN))
        self.assertIsNone(lecture({}, OTAN))

    def test_aiguilles_et_chiffres_d_accord(self):
        """L'aiguille tombe sur son chiffre : mêmes fonctions des deux côtés."""
        from tablette.instruments import (OTAN, WARBIRD_US, angle_badin, angle_vario, cadrans,
                                          lecture)
        for inst in (OTAN, WARBIRD_US):
            c = cadrans(inst)
            for g in c["badin"]:
                self.assertEqual(g["angle"], round(angle_badin(float(g["texte"]), inst), 1))
            self.assertIn("0", [g["texte"] for g in c["vario"]])
            self.assertEqual(next(g for g in c["vario"] if g["texte"] == "0")["angle"], 270.0)
        self.assertEqual(lecture({"vz": 0.0}, OTAN)["vario"]["angle"], 270.0)
        self.assertEqual(angle_vario(99999, OTAN), 270.0 + 170.0)               # butée
        self.assertEqual(lecture({"vi": 999.0}, WARBIRD_US)["badin"]["angle"], 320.0)
        # Altimètre : 5 241 ft → grande aiguille sur 2,4 ; petite sur 5,2.
        alti = lecture({"alt": 5241 * 0.3048}, OTAN)["altimetre"]["angles"]
        self.assertAlmostEqual(alti[0], 0.241 * 360, delta=0.2)
        self.assertAlmostEqual(alti[1], 0.5241 * 360, delta=0.2)
        self.assertEqual([g["texte"] for g in c["g"]], ["-4", "-2", "0", "2", "4", "6", "8"])

    def test_taux_de_virage_tire_du_cap(self):
        from tablette.instruments import TauxDeVirage
        heure = [0.0]
        virage = TauxDeVirage(lambda: heure[0])
        for i in range(100):                    # 3°/s à droite, en passant par le nord
            heure[0] = i * 0.05
            taux = virage.mesurer((350 + 3 * heure[0]) % 360)
        self.assertAlmostEqual(taux, 3.0, places=2)
        heure[0] += 5                           # plus de nouvelles : on repart de zéro
        self.assertEqual(virage.mesurer(10.0), 0.0)

    def test_message_vol_recu_et_interdit(self):
        from tablette.dcs import PontDCS
        pont = PontDCS(0, 0)
        self.assertEqual(pont.vol(), (None, False))
        pont._recevoir("vol vi=100.0000 alt=1500.0000 cap=0.5 inconnu=x")
        vol, interdit = pont.vol()
        self.assertEqual((vol["vi"], vol["alt"], interdit), (100.0, 1500.0, False))
        self.assertIn("taux", vol)
        pont._recevoir("vol -")
        self.assertEqual(pont.vol(), (None, True))

    def test_tous_les_profils_ont_des_instruments(self):
        from tablette.instruments import ALTITUDES, MASSES, VARIOS, VITESSES, cadrans
        for profil in appareils.PROFILS + (appareils.GENERIQUE,):
            i = profil.instruments
            self.assertIn(i.vitesse, VITESSES, profil.id)
            self.assertIn(i.altitude, ALTITUDES, profil.id)
            self.assertIn(i.vario, VARIOS, profil.id)
            self.assertIn(i.carburant, MASSES, profil.id)
            self.assertLess(i.g_min, 0, profil.id)
            for nom in ("badin", "vario"):               # pas de chiffre hors du cadran
                c = cadrans(i)[nom]
                self.assertLessEqual(max(float(g["texte"]) for g in c),
                                     i.vitesse_max if nom == "badin" else i.vario_max, profil.id)
        self.assertEqual(appareils.profil_pour("TF-51D").instruments.vitesse, "mph")
        self.assertEqual(appareils.profil_pour("F4U-1D").instruments.vitesse, "kt")
        self.assertEqual(appareils.profil_pour("Bf-109K-4").instruments.altitude, "m")
        self.assertEqual([g["texte"] for g in cadrans(appareils.profil_pour("Bf-109K-4")
                                                      .instruments)["badin"]][-1], "700")

    def test_unites_reglees_dans_les_options_de_dcs(self):
        """MiG-29 « Avionics Units » sur Imperial, L-39 en anglais : nœuds et
        pieds. Lignes telles que DCS les écrit dans options.lua."""
        mig29, l39 = appareils.profil_pour("MiG-29 Fulcrum"), appareils.profil_pour("L-39C")
        imperial = '\t\t["MiG-29-Fulcrum"] = {\n\t\t\t["MiG29AvionicsUnits"] = 1,\n'
        metrique = '\t\t["MiG-29-Fulcrum"] = {\n\t\t\t["MiG29AvionicsUnits"] = 0,\n'
        self.assertEqual(mig29.instruments_selon(imperial).vitesse, "kt")
        self.assertEqual(mig29.instruments_selon(metrique).vitesse, "km/h")
        self.assertEqual(mig29.instruments_selon("").vitesse, "km/h")
        self.assertEqual(mig29.instruments_selon(imperial).moteurs, 2)
        self.assertEqual(l39.instruments_selon('\t\t["avionicsLanguage"] = "english",').altitude,
                         "ft")
        self.assertEqual(l39.instruments_selon('\t\t["avionicsLanguage"] = "native",').altitude,
                         "m")
        # Une option d'un autre module ne touche pas les autres appareils.
        self.assertEqual(appareils.profil_pour("Su-27").instruments_selon(imperial).vitesse,
                         "km/h")

    def test_api(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        pont = FauxPont(connecte=True, appareil="TF-51D")
        pont.vol = lambda: ({"vi": 100.0}, False)
        client = TestClient(create_app(Config(saved_games=Path(".")), pont,
                                       dossier_dcs=lambda: None))
        d = client.get("/api/instruments").json()
        self.assertEqual((d["interdit"], d["instruments"]["badin"]["texte"]), (False, "224"))
        c = client.get("/api/instruments/cadrans").json()
        self.assertEqual(c["unites"]["vitesse"], "mph")
        self.assertEqual(d["cle"], c["cle"])       # la page garde ses cadrans
        pont.vol = lambda: (None, True)
        self.assertEqual(client.get("/api/instruments").json(),
                         {"interdit": True, "cle": c["cle"], "instruments": None})

    def test_api_suit_les_options_de_dcs(self):
        """Unités du MiG-29 changées dans DCS : la clé change, la page
        redemande ses cadrans."""
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        with tempfile.TemporaryDirectory() as dossier:
            options = Path(dossier) / "Config" / "options.lua"
            options.parent.mkdir()
            options.write_text('["MiG29AvionicsUnits"] = 0,', encoding="utf-8")
            pont = FauxPont(connecte=True, appareil="MiG-29 Fulcrum")
            pont.vol = lambda: ({"vi": 100.0}, False)
            client = TestClient(create_app(Config(saved_games=Path(dossier)), pont,
                                           dossier_dcs=lambda: None))
            avant = client.get("/api/instruments").json()
            self.assertEqual(avant["instruments"]["badin"]["texte"], "360")       # km/h
            options.write_text('["MiG29AvionicsUnits"] = 1,', encoding="utf-8")
            os.utime(options, (time.time() + 10, time.time() + 10))     # DCS l'a réécrit
            apres = client.get("/api/instruments").json()
            self.assertEqual(apres["instruments"]["badin"]["texte"], "194")       # kt
            self.assertNotEqual(apres["cle"], avant["cle"])
            self.assertEqual(client.get("/api/instruments/cadrans").json()["cle"], apres["cle"])

    @unittest.skipUnless(LUA_DCS.exists(), "moteur Lua de DCS absent")
    def test_le_script_lua_envoie_les_donnees_de_vol(self):
        """Le vrai script, dans le moteur Lua de DCS, avec un faux DCS : un
        Christen Eagle II, sans profil, envoie quand même ses données de vol."""
        resultat = executer_lua(FAUX_DCS, SCRIPT_LUA,
                                "LuaExportStart(); LuaExportBeforeNextFrame(); "
                                "HORLOGE = 1; EXPORT_PERMIS = false; LuaExportBeforeNextFrame(); "
                                "RESULTAT = table.concat(ENVOYES, ' | ')")
        messages = resultat.split(" | ")
        self.assertEqual(messages[0], "etat Christen Eagle II")
        vol = dict(m.split("=") for m in messages[1].split()[1:])
        self.assertEqual((vol["vi"], vol["alt"], vol["rpm1"], vol["carb"], vol["train"]),
                         ("100.0000", "1500.0000", "75.0000", "300.0000", "1.0000"))
        self.assertNotIn("vv", vol)              # fonction absente : rien plutôt que zéro
        self.assertIn("vol -", messages)         # serveur qui interdit l'export


class TestLuminosite(unittest.TestCase):
    """Luminosité réglée écran par écran sur la tablette (TGP du F-16 sombre)."""

    def test_courbe_eclaircit_les_gris_sans_toucher_noir_ni_blanc(self):
        from tablette.video import table_luminosite
        for niveau in range(1, 6):
            table = table_luminosite(niveau, 1)
            self.assertEqual((table[0], table[255]), (0, 255))
            self.assertGreater(table[60], 60)
            self.assertEqual(table, sorted(table))           # jamais d'inversion
        self.assertLess(table_luminosite(-2, 1)[128], 128)
        self.assertEqual(table_luminosite(0, 1), list(range(256)))
        self.assertGreater(table_luminosite(4, 1)[40], 2 * 40)   # un TGP sombre ressort

    def test_image_eclaircie_avant_compression_et_par_reglage(self):
        from PIL import Image, ImageStat

        from tablette.ecrans_dcs import NOM_FICHIER, disposition_essai, generer
        from tablette.copie import Copie
        from tablette.video import LUMINOSITE_MAX, Video
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        saved = Path(tmp.name)
        (saved / "Config" / "MonitorSetup").mkdir(parents=True)
        (saved / "Config" / "MonitorSetup" / NOM_FICHIER).write_text(
            generer((0, 0, 2560, 1440), disposition_essai(2560, 1440), "test"), encoding="ascii")
        (saved / "Config" / "options.lua").write_text(
            '["multiMonitorSetup"] = "tablette",\n["width"] = 2560,\n["height"] = 1440,\n',
            encoding="utf-8")
        gris = Image.new("RGB", (480, 480), (40, 40, 40))     # un TGP de nuit
        video = Video(saved, capturer=lambda zones: Copie((2560, 1440), {n: gris for n in zones}),
                      lancement=lambda: None)

        def moyenne(donnees):
            return ImageStat.Stat(Image.open(io.BytesIO(donnees)).convert("L")).mean[0]
        normal, clair = video.image("LEFT_MFCD"), video.image("LEFT_MFCD", 3)
        self.assertAlmostEqual(moyenne(normal), 40, delta=3)
        self.assertGreater(moyenne(clair), 90)
        self.assertNotEqual(video.image("LEFT_MFCD"), clair)    # chaque réglage son image
        self.assertEqual(video.image("LEFT_MFCD", 99), video.image("LEFT_MFCD", LUMINOSITE_MAX))

    def test_api_transmet_le_reglage(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        demandes = []

        class FausseVideo:
            def image(self, viewport, luminosite=0):
                demandes.append((viewport, luminosite))
                return b"\xff\xd8\xff"
        client = TestClient(create_app(Config(saved_games=Path(".")), FauxPont(),
                                       FausseVideo(), dossier_dcs=lambda: None))
        client.cookies.set("tablette_appareil", "fa18c")
        client.get("/api/video/ddi_gauche?lum=3")
        client.get("/api/video/ddi_gauche")
        self.assertEqual([l for _, l in demandes], [3, 0])


class FauxPont:
    """L'état du lien avec DCS, réglé à la main."""

    def __init__(self, a_l_ecoute=True, connecte=False, appareil=None):
        self.a_l_ecoute, self.port_etat = a_l_ecoute, 7791
        self._etat = {"connecte": connecte, "appareil": appareil}

    def etat(self):
        return dict(self._etat)


class TestDiagnostic(unittest.TestCase):
    """La console de diagnostic, sur un faux Saved Games/DCS et des écrans
    décrits : rien du poste n'est lu, réparé ni déplacé."""

    PRINCIPAL = TestInstallation.PRINCIPAL
    VIRTUEL = TestInstallation.VIRTUEL

    def setUp(self):
        from tablette.installation import configurer_ecrans, installer_scripts
        TestInstallation.setUp(self)
        installer_scripts(self.saved)
        configurer_ecrans(self.saved, ecrans=[self.PRINCIPAL, self.VIRTUEL],
                          ouvert=lambda: False)
        self.ecrans = [self.PRINCIPAL, self.VIRTUEL]
        self.lance = False
        self.reseaux = [("Maison", "Private")]
        self.virtuel = ("ok", "« Virtual Display Driver » (2560×1440, 240 Hz)", [])
        self.reparer = []
        self.choix = {}

    def tearDown(self):
        self.tmp.cleanup()

    def test_configuration_du_pilote_gardee_jamais_remplacee(self):
        options = self.saved / "Config" / "options.lua"
        options.write_text(lire(options).replace('"tablette"', '"Mes MFD"'), encoding="utf-8")
        (self.saved / "Config" / "MonitorSetup" / "mesmfd.lua").write_text(
            "name = _('Mes MFD');\nLEFT_MFCD =\n{\n x = 2560;\n y = 0;\n width = 600;\n"
            " height = 600;\n}\n", encoding="utf-8")
        avant = lire(options)
        self.choix = {"mode": "existante", "configuration": "Mes MFD"}
        points = self.points()
        self.assertEqual(points["Écrans de DCS"].etat, "ok")
        self.assertIn("Mes MFD", points["Écran virtuel"].detail)
        self.assertEqual(self.reparer, [])                  # l'écran virtuel n'est pas touché
        self.assertEqual(lire(options), avant)
        options.write_text(avant.replace('"Mes MFD"', '"1camera"'), encoding="utf-8")
        point = self.points()["Écrans de DCS"]
        self.assertEqual(point.etat, "a_faire")
        self.assertIn("1camera", lire(options))             # dit, pas remis d'office

    def test_desinstallation_jamais_annulee_par_le_diagnostic(self):
        """Désinstallé pendant que DCS Tablette tournait : rien n'est remis."""
        from tablette.installation import desinstaller_scripts, retirer_ecrans
        desinstaller_scripts(self.saved)
        retirer_ecrans(self.saved, ouvert=lambda: False)
        options = lire(self.saved / "Config" / "options.lua")
        points = self.points()
        self.assertEqual(points["Installation"].etat, "a_faire")
        self.assertNotIn("Scripts dans DCS", points)
        self.assertEqual(self.reparer, [])
        self.assertFalse((self.saved / "Scripts" / "DCS-Tablette-Export.lua").exists())
        self.assertFalse((self.saved / "Config" / "MonitorSetup" / "tablette.lua").exists())
        self.assertEqual(lire(self.saved / "Config" / "options.lua"), options)
        # La copie d'origine a servi : supprimée, une future installation en prendra une neuve.
        self.assertFalse((self.saved / "Config" / "options.lua.avant-tablette").exists())

    def test_dcs_ouvert_rien_ne_bouge(self):
        """En vol, un écran qui s'endort ne doit pas faire perdre la tablette."""
        fichier = self.saved / "Config" / "MonitorSetup" / "tablette.lua"
        avant = lire(fichier)
        self.lance = True
        self.ecrans = [self.PRINCIPAL, (2560, 0, 1920, 1080, False)]
        point = self.points()["Écrans de DCS"]
        self.assertEqual(point.etat, "a_faire")
        self.assertIn("Quitter DCS", point.solution[0])
        self.assertEqual(lire(fichier), avant)
        self.assertEqual(self.reparer, [False])              # écran virtuel : constaté, pas déplacé

    def test_ecran_reel_pris_seulement_s_il_a_ete_donne(self):
        self.choix = {"mode": "second_ecran", "physique": False}
        self.ecrans = [(0, 0, 2560, 1440, True, False), (2560, 0, 2560, 1440, False, False)]
        self.virtuel = ("manque", "aucun : les écrans du cockpit iraient sur la vue", [])
        points = self.points()
        self.assertEqual(points["Écrans de DCS"].etat, "attente")
        self.assertEqual(self.reparer[-1:], [True])

    def diagnostic(self, **autres):
        from tablette.diagnostic import Diagnostic

        def virtuel(reparer, physique=False):
            self.reparer.append(reparer)
            return self.virtuel
        reglages = dict(ouvert=lambda: self.lance, ecrans=lambda: self.ecrans,
                        virtuel=virtuel, lancement=lambda: None,
                        reseaux=lambda: self.reseaux, choix=lambda: self.choix)
        reglages.update(autres)
        return Diagnostic(self.saved, **reglages)

    def points(self, diagnostic=None, forcer=False):
        diagnostic = diagnostic or self.diagnostic()
        return {p.titre: p for p in diagnostic.verifier(forcer)}

    def test_tout_en_place_rien_a_regler(self):
        d = self.diagnostic()
        points = self.points(d)
        self.assertEqual({p.etat for p in points.values()}, {"ok", "attente"},
                         {t: (p.etat, p.detail) for t, p in points.items()})
        self.assertEqual(points["Écrans de DCS"].detail,
                         "« Tablette DCS » : 4 écrans sur le second écran")
        self.assertEqual(d.etat()["problemes"], 0)
        self.assertEqual(d.etat()["journal"], [])

    def test_scripts_d_une_ancienne_version_recopies(self):
        from tablette.installation import scripts_a_jour
        (self.saved / "Scripts" / "DCS-Tablette-Export.lua").write_text("-- 1.2.1")
        d = self.diagnostic()
        self.assertEqual(self.points(d)["Scripts dans DCS"].etat, "repare")
        self.assertTrue(scripts_a_jour(self.saved))
        self.assertEqual(d.etat()["journal"][0]["titre"], "Scripts dans DCS")
        self.assertEqual(self.points(d)["Scripts dans DCS"].etat, "ok")

    def plein_ecran(self):
        options = self.saved / "Config" / "options.lua"
        options.write_text(lire(options).replace('["fullScreen"] = false', '["fullScreen"] = true')
                           .replace('"tablette"', '"1camera"'), encoding="utf-8")
        return options

    def test_dcs_repasse_en_plein_ecran_remis_dcs_ferme(self):
        options = self.plein_ecran()
        point = self.points()["Réglages de DCS"]
        self.assertEqual(point.etat, "repare")
        self.assertIn("1camera", point.detail)
        self.assertIn('["fullScreen"] = false', lire(options))
        self.assertIn('"tablette"', lire(options))

    def test_dcs_ouvert_ses_reglages_ne_sont_pas_touches(self):
        options = self.plein_ecran()
        avant = lire(options)
        self.lance = True
        point = self.points()["Réglages de DCS"]
        self.assertEqual(point.etat, "a_faire")
        self.assertIn("Quitter DCS", point.solution[0])
        self.assertEqual(lire(options), avant)

    def test_ecran_virtuel_change_configuration_reecrite(self):
        from tablette.ecrans_dcs import zones_actives
        self.ecrans = [self.PRINCIPAL, (2560, 0, 1920, 1080, False)]
        point = self.points()["Écrans de DCS"]
        self.assertEqual(point.etat, "repare")
        for x, y, l, h in zones_actives(self.saved).values():
            self.assertTrue(2560 <= x and x + l <= 4480 and y + h <= 1080)

    def test_configuration_retouchee_a_la_main_gardee(self):
        fichier = self.saved / "Config" / "MonitorSetup" / "tablette.lua"
        retouche = lire(fichier).replace("width = 720;", "width = 700;")
        fichier.write_text(retouche, encoding="ascii")
        self.assertEqual(self.points()["Écrans de DCS"].etat, "ok")
        self.assertEqual(lire(fichier), retouche)

    def test_reseau_public_dit_comment_le_passer_en_prive(self):
        self.reseaux = [("ORBI46 2", "Public")]
        point = self.points()["Réseau du PC"]
        self.assertEqual(point.etat, "a_faire")
        self.assertIn("Privé", point.solution[0])

    def test_ecran_virtuel_rate_pas_reessaye_en_boucle(self):
        self.virtuel = ("manque", "Écran virtuel non placé : Windows refuse", ["À la main"])
        d = self.diagnostic()
        self.points(d)
        self.points(d)
        self.points(d, forcer=True)
        self.assertEqual(self.reparer, [True, False, True])

    def test_signal_de_dcs(self):
        logs = self.saved / "Logs"
        logs.mkdir()
        (logs / "dcs.log").write_text(
            "2026-10-30 21:00:00.000 INFO    DCS-TABLETTE (Main): charge (LuaSocket : oui)\n"
            "2026-10-30 21:00:01.000 ERROR   DCS-TABLETTE (Main): port 7790 deja pris\n",
            encoding="utf-8")
        titre = "Script de la tablette dans DCS"
        self.assertEqual(self.points(self.diagnostic(pont=FauxPont(a_l_ecoute=False)))[titre]
                         .etat, "manque")
        self.assertEqual(self.points(self.diagnostic(pont=FauxPont()))[titre].etat, "attente")
        self.lance = True
        point = self.points(self.diagnostic(pont=FauxPont()))[titre]
        self.assertEqual(point.etat, "a_faire")
        self.assertIn("port 7790 deja pris", point.detail)
        point = self.points(self.diagnostic(pont=FauxPont(connecte=True, appareil="FA-18C_hornet")))[titre]
        self.assertEqual((point.etat, point.detail),
                         ("ok", "DCS parle à la tablette : FA-18C_hornet"))

    def test_une_verification_qui_plante_ne_bloque_rien(self):
        def panne():
            raise OSError("EnumDisplayMonitors")
        points = self.points(self.diagnostic(ecrans=panne))
        self.assertIn("non vérifié", points["Écrans de DCS"].detail)
        self.assertEqual(points["Réseau du PC"].etat, "ok")

    def test_premiere_fois_sans_dossier_de_dcs(self):
        (self.saved / "Config" / "options.lua").unlink()
        points = self.points()
        self.assertEqual(points["Dossier de DCS"].etat, "manque")
        self.assertNotIn("Scripts dans DCS", points)

    def test_la_tablette_vue_par_l_api(self):
        from fastapi.testclient import TestClient

        from tablette.app import create_app
        from tablette.config import Config
        self.reseaux = [("ORBI46 2", "Public")]
        d = self.diagnostic()
        d.verifier()
        client = TestClient(create_app(Config(saved_games=self.saved), FauxPont(),
                                       dossier_dcs=lambda: None, diagnostic=d))
        self.assertEqual(client.get("/api/etat").json()["problemes"], 1)
        self.assertEqual(client.post("/api/diagnostic").status_code, 422)    # POST vide
        corps = client.post("/api/diagnostic", json={"verifier": True}).json()
        tablette = next(p for p in corps["points"] if p["titre"] == "Tablette")
        self.assertEqual(tablette["etat"], "ok")
        self.assertEqual(corps["problemes"], 1)
        self.assertEqual(client.get("/api/diagnostic").json()["points"], corps["points"])

    def test_derniere_ligne_du_script_dans_dcs_log(self):
        from tablette.diagnostic import derniere_ligne_tablette
        self.assertIsNone(derniere_ligne_tablette(self.saved))
        (self.saved / "Logs").mkdir()
        (self.saved / "Logs" / "dcs.log").write_text(
            "2026-10-30 21:00:00.000 INFO    DCS-TABLETTE (Main): pret : appuis ecoutes\n"
            "2026-10-30 21:00:02.000 INFO    EDCORE (Main): autre chose\n", encoding="utf-8")
        self.assertEqual(derniere_ligne_tablette(self.saved), (False, "pret : appuis ecoutes"))


class TestRemettreEcranVirtuel(unittest.TestCase):
    def remettre(self, listes, reparer=True, refus=None):
        from tablette.ecran_virtuel import remettre
        listes = list(listes)
        appels = []

        def appliquer(p):
            appels.append((p.x, p.y))
            return refus
        etat = remettre(reparer, lister=lambda: listes.pop(0) if len(listes) > 1 else listes[0],
                        etendre=lambda: True, appliquer=appliquer, attendre=lambda s: None)
        return etat, appels

    def test_en_place(self):
        (etat, detail, _), appels = self.remettre([[PRINCIPAL, ecran(modes=MODES_VDD)]])
        self.assertEqual((etat, appels), ("ok", []))
        self.assertIn("Virtual Display Driver", detail)

    def test_deplace_remis(self):
        (etat, detail, _), appels = self.remettre(
            [[PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)], [PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)],
             [PRINCIPAL, ecran(modes=MODES_VDD)]])
        self.assertEqual((etat, appels), ("repare", [(2560, 0)]))

    def test_deplace_sans_reparer(self):
        (etat, _, solution), appels = self.remettre([[PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)]],
                                                    reparer=False)
        self.assertEqual((etat, appels), ("a_faire", []))
        self.assertIn("Vérifier", solution[0])

    def test_absent_rien_n_est_installe(self):
        (etat, _, solution), appels = self.remettre([[PRINCIPAL]])
        self.assertEqual((etat, appels), ("manque", []))
        self.assertIn("Installer.bat", solution[0])

    def test_refuse_par_windows(self):
        (etat, detail, solution), _ = self.remettre(
            [[PRINCIPAL, ecran(x=-2560, modes=MODES_VDD)]], refus="Windows refuse ce réglage")
        self.assertEqual(etat, "manque")
        self.assertIn("Windows refuse", detail)
        self.assertIn("Paramètres", solution[0])


if __name__ == "__main__":
    unittest.main()
