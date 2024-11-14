from python_apis.services.ad_ou_service import ADOrganizationalUnitService


def main():
    ad_ou = ADOrganizationalUnitService()
    ad_ou.create_table()
    ad_ou.update_ou_db()

if __name__ == '__main__':
    main()
